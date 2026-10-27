"""Offline corpus/decision contracts. Editorial scores are supplied judgments.

These tests prove inventory, evidence binding and ranking mechanics; they do
not claim to measure a paid model's semantic editorial judgment.
"""
import copy
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from contextlib import nullcontext
from unittest.mock import patch

from core.brief_story_discovery import (
    content_digest, discovery_packet, decision_score, validate_selection, NoQualifyingStory,
    receipt, MAX_DISCOVERY_RECORDS,
)
from scripts.sunday_briefs_auto_writer import choose_evidence, compose
from scripts.sunday_editorial_handoff import main
from tests.test_sunday_source_offer_audit import row, sidecar
from tests.test_weekly_briefs_auto_writer import valid_manuscript

SAT = '2026-10-10'


def source(i, desk='china', *, body=None, **kwargs):
    r = row(i, desk, analyzed=True, passed=1, **kwargs)
    r['processing_state'] = None
    r['source_name'] = desk + ' official institution'
    r['text_original'] = body or ('Distinct development %s at institution %s. ' % (i, desk)) * 12
    r['text_english'] = r['text_original']
    return r


def inventory(rows):
    scaffold = sidecar(rows)
    out = []
    with patch('scripts.sunday_briefs_auto_writer.read_only'), patch(
            'scripts.sunday_briefs_auto_writer.get_articles_for_desks', return_value=rows):
        chosen = choose_evidence(scaffold, as_of=SAT, discovery_inventory=out)
    return chosen, out


def proposal(packet, ids, *, slug='new-capability', values=(4,4,4,0,4), readiness='ready', connection=False):
    by_id = {s['id']: s for s in packet['sources']}
    return dict(slug=slug, thesis='A specific documented institutional change warrants close examination.',
        why_now='The completed development was disclosed during this reporting week.',
        novelty_basis='The documented change differs from the earlier routine baseline.',
        counterevidence='The institutional account does not independently prove operational effects.',
        limitation='No independent operational performance measurements are available.',
        production_ids=[i for i in ids if type(i) is int], research_ids=[i for i in ids if type(i) is str],
        evidence_notes=[dict(id=i, excerpt=by_id[i]['excerpts'][0][:40]) for i in ids],
        counterevidence_ids=[], connection_applicable=connection,
        connection_basis='No comparison is needed for this specific institutional development.',
        score_reasoning='Concrete detail supports these scores, with uncertainty limiting evidence strength.',
        readiness=readiness, scores=dict(zip(('strategic_significance','evidence_strength',
            'analytical_novelty','cross_desk_connection','timeliness'), values)))


def decision(options, lead):
    return dict(candidates=options, selected_slug=lead,
        selection_rationale='The lead has the strongest eligible evidence and concrete verified novelty.',
        omission_rationale='Other clusters have routine activity or lack a verified consequential change.')


class DiscoveryContracts(unittest.TestCase):
    def test_long_preamble_cannot_hide_novelty_or_future_cutoff(self):
        preamble = 'Participants exchanged routine professional observations. ' * 25
        body = (preamble + 'This iteration marks the inaugural deployment of a new capability. '
                'On 28 October, the unit will conduct a future demonstration. '
                'A separate proof of concept was conducted before this week. ')
        summary = preamble + 'The important change appears after the introductory material.'
        digest = content_digest(body, summary)
        self.assertIn('important change', digest['machine_synopsis'])
        excerpts = ' '.join(digest['excerpts'])
        self.assertIn('inaugural deployment', excerpts)
        self.assertIn('28 October', excerpts)
        self.assertIn('was conducted', excerpts)

    def test_place_name_new_zealand_cannot_displace_actual_novelty(self):
        body = ('Australia and New Zealand conduct exchanges with New Zealand participants. '
                'The exercise marks the inaugural deployment of land unmanned systems. ')
        self.assertIn('inaugural deployment', ' '.join(content_digest(body)['excerpts']))

    def test_long_sentence_keeps_closing_limitation_as_an_exact_anchor(self):
        body = ('The unit completed an inaugural test involving ' +
                'several supporting units and their field equipment ' * 7 +
                '; however, this was a simulation and no operational capability was fielded.')
        digest = content_digest(body)
        self.assertIn('inaugural test', ' '.join(digest['excerpts']))
        self.assertIn('no operational capability was fielded', ' '.join(digest['excerpts']))
        self.assertTrue(all(excerpt in body for excerpt in digest['excerpts']))
        self.assertGreater(digest['omitted_body_chars'], 0)
        self.assertLessEqual(sum(map(len, digest['excerpts'])), 360)

    def test_long_sentence_retains_a_cue_after_its_preamble(self):
        body = ('Background detail about participants and equipment, ' * 8 +
                'an inaugural capability trial, ' + 'with supporting personnel, ' * 12 +
                'remains a simulation without operational validation.')
        digest = content_digest(body)
        self.assertIn('inaugural capability trial', ' '.join(digest['excerpts']))
        self.assertIn('without operational validation', ' '.join(digest['excerpts']))
        self.assertTrue(all(excerpt in body for excerpt in digest['excerpts']))

    def test_high_volume_week_offers_all_content_including_stronger_singapore(self):
        rows = [source(i) for i in range(1,41)] + [source(99,'singapore')]
        chosen, audit = inventory(rows)
        packet = discovery_packet(chosen, [], inventory=audit)
        self.assertEqual(len(chosen), 41)
        self.assertEqual({s['id'] for s in packet['sources']}, {r['id'] for r in rows})
        self.assertTrue(all(s['excerpts'] for s in packet['sources']))
        options = [proposal(packet,[1],slug='routine-china',values=(3,4,2,0,4)),
                   proposal(packet,[99],slug='singapore-delta',values=(4,4,4,0,4))]
        self.assertEqual(validate_selection(decision(options,'singapore-delta'),packet)['selected_slug'],
                         'singapore-delta')

    def test_near_duplicate_releases_across_issuers_share_one_cluster(self):
        body = 'A single official exercise release describing the same concrete development. ' * 15
        rows = [source(i,body=body) for i in range(1,7)] + [source(99,'singapore')]
        for i,r in enumerate(rows[:6]):
            r['source_name'] = 'Different republisher %s' % i
            r['summary_english'] = 'Different automated wording %s' % i
        chosen, audit = inventory(rows)
        packet = discovery_packet(chosen,[],inventory=audit)
        self.assertEqual(len(packet['clusters']),2)
        self.assertEqual(set(packet['clusters'][0]['source_ids']),set(range(1,7)))
        # Renaming an idea while retaining the same evidence cannot multiply slots.
        # Different numeric records republishing the same story must not evade
        # deduplication merely by avoiding shared record IDs.
        a = proposal(packet,[1]); b=proposal(packet,[2],slug='another-title')
        with self.assertRaisesRegex(ValueError,'duplicate stories'):
            validate_selection(decision([a,b],a['slug']),packet)

    def test_low_volume_desk_is_not_cut_off_by_flags_or_source_count(self):
        rows = [source(i, significant=True) for i in range(1,25)] + [source(99,'korea')]
        chosen,_=inventory(rows)
        self.assertIn(99,[r['id'] for r,b in chosen])
        p=discovery_packet(chosen,[])
        winner=proposal(p,[99],values=(5,4,4,0,5))
        other=proposal(p,[1],slug='familiar-theme',values=(3,3,3,0,3))
        validate_selection(decision([other,winner],winner['slug']),p)

    def test_single_country_beats_weak_forced_comparison(self):
        p=discovery_packet([(r,r['text_original']) for r in [source(1),source(2,'singapore'),source(3,'korea'),
            source(4,body='A separate personnel policy changes qualification requirements and training assessment. '*12)]],[])
        single=proposal(p,[1],values=(4,4,4,0,4))
        multi=proposal(p,[2,3],slug='regional-comparison',values=(3,3,3,5,3),connection=True)
        self.assertGreater(decision_score(single),decision_score(multi))
        third=proposal(p,[4],slug='secondary-local-story',values=(2,3,2,0,3))
        validate_selection(decision([single,multi,third],single['slug']),p)

    def test_compelling_unscreened_korea_is_held_and_recorded(self):
        r=source(99,'korea',significant=True);r['analyzed_at']=None;r['passed_relevance']=None
        chosen,audit=inventory([source(1),r])
        self.assertEqual([x['id'] for x,b in chosen],[1])
        self.assertEqual(audit[-1]['reason'],'awaiting_screening_or_analysis')

    def test_metadata_derived_and_rights_holds_cannot_supply_bodies(self):
        rows=[source(1),source(2),source(3),source(4)]
        rows[1]['text_original']='';rows[2]['processing_state']='paused';rows[3]['title_original']=''
        chosen,audit=inventory(rows)
        self.assertEqual([x['id'] for x,b in chosen],[1])
        self.assertEqual({x['reason'] for x in audit}, {'eligible','processing_hold',
                         'no_original_full_text_metadata_or_derived_record'})
        p=discovery_packet(chosen,[]);bad=proposal(p,[1]);bad['production_ids']=[2]
        with self.assertRaisesRegex(ValueError,'unavailable'):
            validate_selection(decision([bad],bad['slug']),p)

    def test_routine_exercise_cannot_win_on_scale(self):
        p=discovery_packet([(r,r['text_original']) for r in [source(1),source(2,'singapore')]],[])
        routine=proposal(p,[1],values=(5,5,1,0,5));routine['novelty_basis']='The claimed first appeared in earlier annual exercises; no new delta.'
        real=proposal(p,[2],slug='verified-change',values=(3,3,3,0,3))
        validate_selection(decision([routine,real],real['slug']),p)
        with self.assertRaisesRegex(ValueError,'floors'):
            validate_selection(decision([routine,real],routine['slug']),p)

    def test_anchored_minority_counterevidence_changes_eligible_ranking(self):
        p=discovery_packet([(r,r['text_original']) for r in [source(1),source(2,'singapore'),source(3)]],[])
        a=proposal(p,[1],values=(5,4,4,0,5)); b=proposal(p,[2],slug='alternative',values=(4,4,4,0,4))
        validate_selection(decision([a,b],a['slug']),p)
        # A contrary preserved source changes the editorial assessment; code
        # checks its exact offered content and recomputes the resulting ranking.
        a['evidence_notes'].append(dict(id=3,excerpt=next(
            s for s in p['sources'] if s['id']==3)['excerpts'][0][:40]))
        a['counterevidence_ids']=[3];a['scores']['evidence_strength']=2
        a['counterevidence']='The contrary account undermines the claimed completed capability.'
        a['score_reasoning']='This contrary source reduces evidence below the minimum commitment floor.'
        validate_selection(decision([a,b],b['slug']),p)
        a['evidence_notes'][-1]['excerpt']='An invented quotation absent from all offered content.'
        with self.assertRaisesRegex(ValueError,'content anchor'):
            validate_selection(decision([a,b],b['slug']),p)

    def test_high_total_weak_evidence_loses_to_substantiated_alternative(self):
        p=discovery_packet([(r,r['text_original']) for r in [source(1),source(2,'singapore')]],[])
        weak=proposal(p,[1],values=(5,2,5,0,5));good=proposal(p,[2],slug='supported-story',values=(3,4,3,0,3))
        self.assertGreater(decision_score(weak),decision_score(good))
        validate_selection(decision([weak,good],good['slug']),p)

    def test_explicit_abstention_skips_prose_validation_and_email(self):
        rows=[source(1),source(2,'singapore')];chosen=[(r,r['text_original']) for r in rows]
        p=discovery_packet(chosen,[]);option=proposal(p,[1],values=(5,2,5,0,5))
        outcome=decision([option],None)
        fake=SimpleNamespace(messages=SimpleNamespace(stream=lambda **kw:nullcontext(SimpleNamespace(
            get_final_message=lambda:SimpleNamespace(stop_reason='tool_use',content=[SimpleNamespace(
                type='tool_use',name='compose_editorial_draft',input={
                    **dict.fromkeys(valid_manuscript(), ''), 'story_selection':outcome,
                    'citations': {k: [] for k in valid_manuscript()['citations']}})])))))
        with patch('scripts.sunday_briefs_auto_writer.choose_evidence',return_value=chosen):
            with self.assertRaises(NoQualifyingStory):
                compose(sidecar(rows),SAT,client=fake,automatic_story_selection=True)
        with tempfile.TemporaryDirectory() as tmp:
            src=Path(tmp)/'scaffold.json';draft=sidecar(rows)
            draft.update(week_start='2026-10-11',week_ending='2026-10-17')
            src.write_text(json.dumps(draft))
            out=Path(tmp)/'draft.txt'
            with patch('scripts.sunday_briefs_auto_writer.compose',side_effect=NoQualifyingStory(outcome)),patch(
                    'scripts.sunday_editorial_handoff.send_packet') as send:
                main(['--sidecar',str(src),'--out',str(out),'--write-automatic','--full-week','--as-of','2026-10-17','--send'])
            send.assert_not_called();self.assertFalse(out.exists())
            self.assertEqual(json.loads(out.with_suffix('.selection.json').read_text())['selected_slug'],None)
            self.assertEqual(out.with_suffix('.selection.json').stat().st_mode & 0o777,0o600)

    def test_overflow_refuses_without_silent_sampling_or_paid_retry(self):
        r=source(1)
        with self.assertRaisesRegex(ValueError,'record budget'):
            discovery_packet([(dict(r,id=i),r['text_original']) for i in range(MAX_DISCOVERY_RECORDS+1)],[])
        fake=SimpleNamespace(messages=SimpleNamespace(stream=unittest.mock.Mock(return_value=nullcontext(
            SimpleNamespace(get_final_message=lambda:SimpleNamespace(stop_reason='max_tokens',content=[]))))))
        with patch('scripts.sunday_briefs_auto_writer.choose_evidence',return_value=[(r,r['text_original'])]):
            with self.assertRaisesRegex(ValueError,'structured tool'):
                compose(sidecar([r]),SAT,client=fake,automatic_story_selection=True)
        self.assertEqual(fake.messages.stream.call_count,1)

    def test_receipt_preserves_scope_and_fingerprints_without_source_bodies(self):
        r=source(1);p=discovery_packet([(r,r['text_original'])],[])
        report=receipt(p)
        self.assertEqual(report['source_pins'][0]['id'],1)
        self.assertIn('omitted_body_chars', report['source_pins'][0])
        self.assertNotIn(r['text_original'],json.dumps(report))
        self.assertIs(report['publication_authorized'],False)
