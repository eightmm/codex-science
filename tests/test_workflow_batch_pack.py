"""Synthetic batch fixtures, hand arithmetic, refusal order and immutable admission."""
import copy
import hashlib
import importlib
import json
import math
import os
from pathlib import Path
import random
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / 'examples/workflow-batch-effect-assessment'
CLI = ROOT / 'scripts/validate_batch_effect_assessment_pack.py'
CALL_TIMEOUT = float(os.environ.get('OMS_TEST_CALL_TIMEOUT', '30'))
CASES = (
    ('confounded-absence', 'confounded-absence'),
    ('confounded-text', 'confounded-absence'),
    ('collinear-adjustment', 'group-adjustment'),
    ('adjusted-text', 'group-adjustment'),
    ('unstratified-permutation', 'permutation-strata'),
    ('group-filter', 'feature-filter'),
    ('sample-drop', 'sample-drop'),
    ('post-outcome-threshold', 'post-outcome-threshold'),
    ('unavailable-batch', 'unavailable-batch'),
    ('corrected', 'claim-boundary'),
    ('removed', 'claim-boundary'),
    ('biological-signal', 'claim-boundary'),
    ('differential-expression', 'claim-boundary'),
    ('mechanism', 'claim-boundary'),
    ('clinical', 'claim-boundary'),
    ('causal', 'claim-boundary'),
    ('physical-validity', 'claim-boundary'),
    ('review-truth', 'claim-boundary'),
    ('review-approval', 'non-evidence'),
    ('computed-kind', 'non-evidence'),
    ('computed-result', 'non-evidence'),
    ('empty-evidence', 'claim-support'),
    ('unavailable-positive', 'unavailable-positive'),
    ('unavailable-evidence', 'unavailable-evidence'),
    ('outside-alias', 'evidence-independence'),
    ('replicated', 'claim-replication'),
    ('late-freeze', 'rule-freeze'),
)


class FixtureCase(unittest.TestCase):
    def setUp(self):
        self.api = importlib.import_module('codex_science.batch_effect_assessment_pack')
        self.pack = json.loads((FIXTURE / 'pack.json').read_bytes())
        self.rules = json.loads((FIXTURE / 'rules.json').read_bytes())
        self.matrix = json.loads((FIXTURE / 'matrix.json').read_bytes())

    def folder(self):
        scratch = tempfile.TemporaryDirectory()
        self.addCleanup(scratch.cleanup)
        folder = Path(scratch.name) / 'parent' / 'bundle'
        shutil.copytree(FIXTURE, folder)
        return folder

    def write(self, folder, name, value):
        raw = (json.dumps(value, sort_keys=True, allow_nan=False) + '\n').encode()
        (folder / name).write_bytes(raw)
        return {'path': name, 'sha256': hashlib.sha256(raw).hexdigest()}

    def run_pack(self, folder):
        self.write(folder, 'pack.json', self.pack)
        return self.api.validate_batch_effect_assessment_pack(folder / 'pack.json')

    def change_input(self, folder, name, value):
        identity = self.write(folder, name + '.json', value)
        self.pack['inputs'][name] = identity
        if name == 'rules':
            self.pack['frozen_rules_sha256'] = identity['sha256']

    def compute(self):
        return self.api.reference_computation(self.rules, self.matrix)

    def observed(self, folder, kind='observed-technical-record', result='batch-structure'):
        record = {'schema':'batch-effect-evidence-v1', 'schema_version':1, 'fixture':True,
                  'kind':kind, 'result':result}
        return self.write(folder, 'observed.json', record)

    def positive(self, identity):
        self.pack['claims'][0].update(status='supported', text='The synthetic technical record is supported.',
                                      support=[dict(identity, origin='study')])


class BatchComputationTests(FixtureCase):
    def test_balanced_fixture_and_hand_arithmetic(self):
        result = self.api.validate_batch_effect_assessment_pack(FIXTURE / 'pack.json')
        self.assertEqual(json.loads((FIXTURE / 'expected.json').read_bytes()), result)
        self.assertEqual(result, self.api.validate_batch_effect_assessment_pack(FIXTURE / 'pack.json'))
        assessment = result['assessment']
        self.assertEqual('batch-structure-detected', assessment['status'])
        self.assertEqual({'rank':3, 'columns':3, 'confounded':False, 'single_batch_groups':[]}, assessment['confounding'])
        metrics = assessment['metrics']
        for feature in metrics['per_feature']:
            self.assertAlmostEqual(2 / 3, feature['batch']['r_squared'])
            self.assertAlmostEqual(12, feature['batch']['f'])
            self.assertAlmostEqual(1 / 6, feature['group']['r_squared'])
            self.assertAlmostEqual(6 / 5, feature['group']['f'])
        self.assertAlmostEqual(2 / 3, metrics['median_batch_r2'])
        self.assertAlmostEqual(1 / 6, metrics['median_group_r2'])
        self.assertAlmostEqual(2 / 3, metrics['batch_silhouette'])
        self.assertAlmostEqual(1 / 10, metrics['group_silhouette'])
        self.assertAlmostEqual(12, metrics['batch_permanova']['pseudo_f'])
        self.assertEqual(0.075, metrics['batch_permanova']['p_value'])
        self.assertAlmostEqual(4 * math.sqrt(5), metrics['qc_dispersion']['rms_distance'])
        self.assertEqual(0, metrics['qc_dispersion']['distance_sd'])
        self.assertEqual(1, assessment['missing_counts']['fixture-missing'])
        self.assertEqual(['missing-values','zero-variance'], [row['reason'] for row in assessment['filtered_features']])
        self.assertEqual('arithmetic-only', result['evidence_level'])
        self.assertEqual('unavailable', result['review'])
        self.assertEqual(list(self.api.STAGES), result['stages'])

    def test_confounded_fixture_is_unassessable(self):
        result = self.api.validate_batch_effect_assessment_pack(FIXTURE / 'confounded.pack.json')
        self.assertEqual(json.loads((FIXTURE / 'confounded.expected.json').read_bytes()), result)
        assessment = result['assessment']
        self.assertEqual('unassessable', assessment['status'])
        self.assertEqual(2, assessment['confounding']['rank'])
        self.assertEqual(3, assessment['confounding']['columns'])
        self.assertIsNone(assessment['metrics'])
        self.assertEqual(['confounded-design'], assessment['failed_controls'])

    def test_exact_rank_covariates_and_single_batch_rule(self):
        self.assertEqual(2, self.api._rank([[1,1], [1,1.0000000000000002]]))
        self.assertEqual(1, self.api._rank([[1,2], [2,4]]))
        self.rules['covariates'] = ['duplicate-batch']
        for row in self.rules['samples']:
            row['covariates'] = {'duplicate-batch':int(row['batch'] == 'B')}
        assessment = self.compute()
        self.assertEqual('unassessable', assessment['status'])
        self.assertEqual(3, assessment['confounding']['rank'])
        self.assertEqual(4, assessment['confounding']['columns'])
        self.rules['covariates'] = []
        for row in self.rules['samples']:
            row['covariates'] = {}
            if row['group'] == 'X':
                row['batch'] = 'A'
        assessment = self.compute()
        self.assertEqual(3, assessment['confounding']['rank'])
        self.assertEqual(['X'], assessment['confounding']['single_batch_groups'])
        self.assertEqual('unassessable', assessment['status'])

    def test_permutation_implementation_preserves_every_group(self):
        original = self.api._permutation_labels
        seen = []
        def check(labels, strata, generator):
            shuffled = original(labels, strata, generator)
            for indices in strata:
                self.assertEqual(sorted(labels[i] for i in indices), sorted(shuffled[i] for i in indices))
            seen.append(tuple(shuffled))
            return shuffled
        with patch.object(self.api, '_permutation_labels', side_effect=check):
            first = self.compute()
        self.assertEqual(199, len(seen))
        self.assertGreater(len(set(seen)), 1)
        self.assertEqual(first, self.compute())
        self.rules['permutations']['seed'] = 0
        self.assertEqual(0, self.compute()['metrics']['batch_permanova']['seed'])

    def test_numerically_tied_permutations_count_as_exceedances(self):
        self.matrix['features'] = ['fixture-tied']
        self.matrix['values'] = [[2, 4, 2, 1, 3, 4, 4, 5]]
        self.rules['permutations'].update(seed=1729, count=99)
        # Exact arithmetic: observed pseudo-F is 1/17 and every permutation reaches it.
        self.assertEqual(1.0, self.compute()['metrics']['batch_permanova']['p_value'])

    def test_tie_tolerance_is_relative_and_keeps_near_zero_statistics_distinct(self):
        self.matrix['features'] = ['fixture-near-zero']
        self.matrix['values'] = [[0, 0, 1, 1, 10000000, 10000000, 10000001, 10000001]]
        # Observed pseudo-F is about 6e-14; smaller permuted statistics must not count as ties.
        self.assertEqual(0.075, self.compute()['metrics']['batch_permanova']['p_value'])

    def test_inclusive_detection_and_qc_thresholds(self):
        metrics = self.compute()['metrics']
        self.rules['thresholds'].update(median_batch_r2=metrics['median_batch_r2'],
            batch_silhouette=metrics['batch_silhouette'], permutation_alpha=metrics['batch_permanova']['p_value'],
            qc_dispersion=metrics['qc_dispersion']['rms_distance'])
        self.assertEqual('batch-structure-detected', self.compute()['status'])
        for key, value in [('median_batch_r2',1), ('batch_silhouette',1), ('permutation_alpha',0)]:
            old = self.rules['thresholds'][key]
            self.rules['thresholds'][key] = value
            self.assertEqual('not-detected', self.compute()['status'])
            self.rules['thresholds'][key] = old
        self.rules['thresholds']['qc_dispersion'] = math.nextafter(metrics['qc_dispersion']['rms_distance'], 0)
        result = self.compute()
        self.assertEqual('unassessable', result['status'])
        self.assertEqual(['qc-dispersion'], result['failed_controls'])
        self.rules['thresholds']['qc_dispersion'] = 0
        self.assertEqual('unassessable', self.compute()['status'])

    def test_missingness_transform_exploratory_and_unavailable_qc(self):
        original = copy.deepcopy(self.matrix)
        self.rules['transformation'] = 'log2p1'
        result = self.compute()
        self.assertEqual(original, self.matrix)
        self.assertEqual(1, result['missing_counts']['fixture-missing'])
        self.matrix['values'][0][0] = -1
        with self.assertRaisesRegex(ValueError, '^transformation:'):
            self.compute()
        self.matrix = original
        self.rules['thresholds_changed_after_outcomes'] = True
        self.rules['exploratory'] = True
        for row in self.rules['samples']:
            row['qc'] = False
        result = self.compute()
        self.assertTrue(result['exploratory'])
        self.assertEqual({'status':'unavailable', 'pairs':0, 'rms_distance':None, 'distance_sd':None}, result['metrics']['qc_dispersion'])
        self.rules['samples'].append({'id':'fixture-unavailable','batch':None,'group':None,'covariates':{},
                                      'available':False,'reason':'Missing synthetic specimen.','qc':False,'replicate':None})
        result = self.compute()
        self.assertEqual(8, result['sample_count'])
        self.assertEqual([{'id':'fixture-unavailable','reason':'Missing synthetic specimen.'}], result['unavailable_samples'])

    def test_failed_permutations_count_and_unexpected_errors_propagate(self):
        self.rules['permutations'].update(count=4, minimum_success_fraction=0.5)
        original = self.api._pseudo
        draws = 0
        def fail_half(features, partition, code='degenerate-data'):
            nonlocal draws
            if code == 'permutation-degenerate':
                draws += 1
                if draws % 2:
                    raise ValueError('permutation-degenerate: injected data failure')
            return original(features, partition, code)
        with patch.object(self.api, '_pseudo', side_effect=fail_half):
            result = self.compute()['metrics']['batch_permanova']
        self.assertEqual(2, result['successful'])
        self.assertGreaterEqual(result['p_value'], 3 / 5)
        self.rules['permutations']['minimum_success_fraction'] = 0.51
        with patch.object(self.api, '_pseudo', side_effect=fail_half), self.assertRaisesRegex(ValueError, '^permutation-success:'):
            self.compute()
        def unexpected(features, partition, code='degenerate-data'):
            if code == 'permutation-degenerate':
                raise ValueError('unexpected: injected')
            return original(features, partition, code)
        with patch.object(self.api, '_pseudo', side_effect=unexpected), self.assertRaisesRegex(ValueError, '^unexpected:'):
            self.compute()

    def test_degenerate_and_extremely_small_values(self):
        baseline = self.compute()['metrics']
        for row in self.matrix['values']:
            for i, value in enumerate(row):
                if value is not None:
                    row[i] = value * 1e-200
        scaled = self.compute()['metrics']
        self.assertAlmostEqual(baseline['median_batch_r2'], scaled['median_batch_r2'])
        self.assertAlmostEqual(baseline['batch_permanova']['pseudo_f'], scaled['batch_permanova']['pseudo_f'])
        self.matrix['features'] = ['constant']
        self.matrix['values'] = [[0]*8]
        with self.assertRaisesRegex(ValueError, '^degenerate-data:'):
            self.compute()
        self.matrix['values'] = [[0,0,1,1,0,0,1,1]]
        with self.assertRaisesRegex(ValueError, '^degenerate-data:'):
            self.compute()
        self.rules['minimum_samples'] = 9
        with self.assertRaisesRegex(ValueError, '^insufficient-samples:'):
            self.compute()


class BatchRefusalTests(FixtureCase):
    def test_negative_manifest_matches_real_cases(self):
        cases = json.loads((FIXTURE / 'negative-cases.json').read_bytes())['cases']
        self.assertEqual(list(CASES), [(case['id'],case['finding']) for case in cases])
        self.assertTrue(all((FIXTURE / case['path']).is_file() for case in cases))

    def test_positive_record_and_outside_identity_checks(self):
        folder = self.folder()
        identity = self.observed(folder)
        self.positive(identity)
        self.assertEqual('supported', self.run_pack(folder)['claims'][0]['status'])
        self.pack['claims'][0]['support'][0]['origin'] = 'external'
        self.assertEqual('supported', self.run_pack(folder)['claims'][0]['status'])
        self.pack['study_outputs'] += [identity]
        with self.assertRaisesRegex(ValueError, '^evidence-independence:'):
            self.run_pack(folder)
        alias = dict(identity, path='alias.json')
        shutil.copyfile(folder / 'observed.json', folder / 'alias.json')
        self.pack['claims'][0]['support'] = [dict(alias,origin='preregistered')]
        with self.assertRaisesRegex(ValueError, '^evidence-independence:'):
            self.run_pack(folder)
        self.pack['claims'][0]['support'] = [dict(self.pack['inputs']['matrix'],origin='external')]
        with self.assertRaisesRegex(ValueError, '^evidence-independence:'):
            self.run_pack(folder)

    def test_arithmetic_and_result_schema_are_non_evidence(self):
        folder = self.folder()
        for field in ('kind', 'result'):
            for value in ('arithmetic-only', 'batch-effect-result-v1'):
                with self.subTest(field=field, value=value):
                    identity = self.observed(folder, **{field: value})
                    self.positive(identity)
                    with self.assertRaisesRegex(ValueError, '^non-evidence:'):
                        self.run_pack(folder)
                    # The exact evidence whitelist also refuses these records.
                    self.assertIsNotNone(self.api.NON_EVIDENCE.search(value))

    def test_unavailable_citations_all_statuses_and_mixed_support(self):
        folder = self.folder()
        observed = self.observed(folder)
        for field in ('kind','result'):
            record = {'schema':'batch-effect-evidence-v1','schema_version':1,'fixture':True,
                      'kind':'observed-technical-record','result':'batch-structure'}
            record[field] = 'unavailable'
            unavailable = self.write(folder,'unavailable.json',record)
            for status in sorted(self.api.STATUSES - {'unavailable'}):
                with self.subTest(field=field,status=status):
                    self.pack['claims'][0].update(status=status,text='The synthetic record is inconclusive.',
                        support=[dict(observed,origin='study'),dict(unavailable,origin='study')])
                    with self.assertRaisesRegex(ValueError,'^unavailable-evidence:'):
                        self.run_pack(folder)
            self.pack['claims'][0]['status'] = 'unavailable'
            self.assertEqual('unavailable', self.run_pack(folder)['claims'][0]['status'])

    def test_wording_families_and_boundary_refusal_order(self):
        folder = self.folder()
        for text in ('causal','mechanistic','therapeutic','clinical','efficacy','effective','treatment','cure',
                     'prevention','recommended','prescription','binding','affinity','inhibition','activation',
                     'regulation','drive','drives','driven','induction','physical-validity','biological-signal',
                     'differential-expression','corrected','removal'):
            with self.subTest(text=text):
                self.pack['claims'][0].update(text=text, status='supported',support=[])
                with self.assertRaisesRegex(ValueError,'^claim-boundary:'):
                    self.run_pack(folder)
        for text in ('supported','replicated','suggestive','significant'):
            self.pack['claims'][0].update(text=text,status='unavailable',support=[])
            with self.assertRaisesRegex(ValueError,'^unavailable-positive:'):
                self.run_pack(folder)

    def test_unhashable_and_wrong_field_types_are_labelled(self):
        folder = self.folder()
        base = copy.deepcopy(self.pack)
        for key in ('status','kind','id','text'):
            self.pack = copy.deepcopy(base)
            self.pack['claims'][0][key] = []
            with self.subTest(key=key), self.assertRaisesRegex(ValueError,'^invalid-record:'):
                self.run_pack(folder)
        self.pack = copy.deepcopy(base)
        identity = self.observed(folder)
        self.positive(identity)
        self.pack['claims'][0]['support'][0]['origin'] = []
        with self.assertRaisesRegex(ValueError,'^invalid-record:'):
            self.run_pack(folder)
        self.pack = copy.deepcopy(base)
        self.pack['status'] = []
        with self.assertRaisesRegex(ValueError,'^invalid-record:'):
            self.run_pack(folder)

    def test_integer_fields_and_boolean_controls_are_strict(self):
        for field in ('seed','count','minimum_samples','schema_version'):
            for value in (True,2.0,'2',None,[],0,-1):
                rules = copy.deepcopy(self.rules)
                target = rules['permutations'] if field in ('seed','count') else rules
                target[field] = value
                if field == 'seed' and value == 0 and type(value) is int:
                    self.api._rules(rules)
                    continue
                with self.subTest(field=field,value=value), self.assertRaisesRegex(ValueError,'^[a-z-]+:'):
                    self.api._rules(rules)
        for field in ('seed','count'):
            rules = copy.deepcopy(self.rules)
            rules['permutations'][field] = 2**32 - 1 if field == 'seed' else self.api.MAX_PERMUTATIONS
            self.api._rules(rules)
            rules['permutations'][field] += 1
            with self.assertRaisesRegex(ValueError,'^invalid-record:'):
                self.api._rules(rules)
        for name in ('pack','matrix','evidence'):
            for value in (True,1.0,'1'):
                folder = self.folder()
                self.pack = json.loads((FIXTURE / 'pack.json').read_bytes())
                record = json.loads((FIXTURE / (name + '.json')).read_bytes())
                record['schema_version'] = value
                if name == 'pack':
                    self.pack = record
                elif name == 'matrix':
                    self.change_input(folder,name,record)
                else:
                    self.pack['study_outputs'] = [self.write(folder,name + '.json',record)]
                with self.subTest(name=name,value=value), self.assertRaisesRegex(ValueError,'^invalid-record:'):
                    self.run_pack(folder)
        for key in ('available','qc'):
            rules = copy.deepcopy(self.rules)
            rules['samples'][0][key] = 1
            with self.assertRaisesRegex(ValueError,'^invalid-record:'):
                self.api._rules(rules)

    def test_identity_shape_and_rule_failures(self):
        for target, field, code in [('matrix','samples','duplicate-identity'),('matrix','features','duplicate-identity')]:
            matrix = copy.deepcopy(self.matrix)
            matrix[field][1] = matrix[field][0]
            with self.subTest(field=field), self.assertRaisesRegex(ValueError,'^'+code+':'):
                self.api.reference_computation(self.rules,matrix)
        for value in ([],[],[[1]],None):
            matrix = copy.deepcopy(self.matrix)
            if value is None:
                matrix['samples'][0] = 'unknown-fixture'
                code = 'sample-coverage'
            else:
                matrix['values'] = value
                code = 'invalid-record|matrix-shape'
            with self.assertRaisesRegex(ValueError,'^(?:'+code+'):'):
                self.api.reference_computation(self.rules,matrix)
        self.rules['samples'][2]['replicate'] = self.rules['samples'][4]['replicate']
        with self.assertRaisesRegex(ValueError,'^replicate-definition:'):
            self.compute()


def _seeded_test(name, code):
    def test(self):
        with self.assertRaisesRegex(ValueError,'^'+code+':'):
            self.api.validate_batch_effect_assessment_pack(FIXTURE / ('negative.' + name + '.pack.json'))
    return test


for _name, _code in CASES:
    setattr(BatchRefusalTests,'test_seeded_' + _name.replace('-','_'),_seeded_test(_name,_code))


class BatchBoundaryTests(FixtureCase):
    def test_cli_success_refusals_help_and_no_writes(self):
        folder = self.folder()
        before = {p.name:p.read_bytes() for p in folder.iterdir() if p.is_file()}
        for arguments, code in [([str(folder/'pack.json')],0),([],2),
                ([str(folder/'pack.json'),'extra'],2),(['--unknown'],2),
                ([str(folder/'pack.json'),'--output','out.json'],2),
                ([str(folder/'negative.confounded-absence.pack.json')],2),(['--help'],0)]:
            run = subprocess.run([sys.executable,str(CLI),*arguments],capture_output=True,text=True,timeout=CALL_TIMEOUT)
            self.assertEqual(code,run.returncode,run.stderr)
            self.assertNotIn('Traceback',run.stderr)
            if code == 2:
                result = json.loads(run.stderr)
                self.assertEqual('refused',result['status'])
                self.assertTrue(result['finding'].startswith('invalid-arguments:' if arguments != [str(folder/'negative.confounded-absence.pack.json')] else 'confounded-absence:'))
                self.assertEqual('',run.stdout)
            elif arguments == ['--help']:
                self.assertIn('usage:',run.stdout)
                self.assertEqual('',run.stderr)
            else:
                self.assertEqual('arithmetic-only',json.loads(run.stdout)['evidence_level'])
                self.assertEqual('',run.stderr)
        self.assertEqual(before,{p.name:p.read_bytes() for p in folder.iterdir() if p.is_file()})

    def test_duplicate_deep_nonobject_nonfinite_and_huge_json(self):
        for raw in (b'{"a":1,"a":2}',b'{"x":{"a":1,"a":2}}',b'[]',b'null',b'{',
                    b'{"x":NaN}',b'{"x":Infinity}',b'{"x":1e999}',
                    b'{"x":'+b'9'*5000+b'}',b'\xff',b'{"x":'+b'['*2000+b'0'+b']'*2000+b'}'):
            with self.subTest(raw=raw[:40]), self.assertRaisesRegex(ValueError,'^invalid-json:'):
                self.api._json(raw,self.api.MAX_TOTAL_NODES)
        with patch.object(re,'findall',side_effect=AssertionError('match lists are forbidden')):
            self.api.validate_batch_effect_assessment_pack(FIXTURE/'pack.json')
        with patch.object(self.api.json,'loads',side_effect=AssertionError('must refuse before parsing')):
            with self.assertRaisesRegex(ValueError,'^input-limit:'):
                self.api._json(b'{"x":[1,2,3]}',2)

    def test_empty_zero_malformed_and_limit_dimensions(self):
        for constant, equal in [('MAX_SAMPLES',8),('MAX_FEATURES',4),('MAX_VALUES',32),
                ('MAX_PERMUTATIONS',199),('MAX_METRIC_WORK',8*4*199),('MAX_CLAIMS',1),('MAX_SUPPORT',1)]:
            with self.subTest(constant=constant), patch.object(self.api,constant,equal):
                self.api.validate_batch_effect_assessment_pack(FIXTURE/'pack.json')
            for limit in (equal-1,0):
                with patch.object(self.api,constant,limit), self.assertRaisesRegex(ValueError,'^input-limit:|^invalid-record:'):
                    self.api.validate_batch_effect_assessment_pack(FIXTURE/'pack.json')
        with patch.object(self.api,'MAX_COVARIATES',0):
            self.compute()
            self.rules['covariates'] = ['fixture-covariate']
            with self.assertRaisesRegex(ValueError,'^input-limit:'):
                self.compute()
        self.rules['covariates'] = []
        for field in ('samples','features','values'):
            for value in ([],None,0,{},'malformed'):
                matrix = copy.deepcopy(self.matrix)
                matrix[field] = value
                with self.subTest(field=field,value=value), self.assertRaisesRegex(ValueError,'^[a-z-]+:'):
                    self.api.reference_computation(self.rules,matrix)
        self.rules['samples'] += [copy.deepcopy(self.rules['samples'][0]) for _ in range(self.api.MAX_SAMPLES)]
        with patch.object(self.api,'_rank',side_effect=AssertionError('count must be checked first')):
            with self.assertRaisesRegex(ValueError,'^input-limit:'):
                self.compute()
        for key in ('median_batch_r2','batch_silhouette','permutation_alpha','qc_dispersion'):
            rules = json.loads((FIXTURE/'rules.json').read_bytes())
            for value in (True,[],None,'0',float('inf'),-2):
                rules['thresholds'][key] = value
                with self.subTest(key=key,value=value), self.assertRaisesRegex(ValueError,'^invalid-record:'):
                    self.api._rules(rules)
        for value in (0,1,4):
            rules = json.loads((FIXTURE/'rules.json').read_bytes())
            rules['permutations']['count'] = value
            if value:
                self.api.reference_computation(rules,self.matrix)
            else:
                with self.assertRaisesRegex(ValueError,'^invalid-record:'):
                    self.api._rules(rules)

    def test_aggregate_byte_node_and_artifact_limits(self):
        records = [(FIXTURE/name).read_bytes() for name in ('pack.json','rules.json','matrix.json','evidence.json')]
        byte_count = sum(map(len,records))
        node_count = sum(1+raw.count(b',')+sum(1 for _ in re.finditer(rb'[\[{](?=\s*[^\s\]}])',raw)) for raw in records)
        for constant, count in [('MAX_TOTAL_BYTES',byte_count),('MAX_TOTAL_NODES',node_count),('MAX_ARTIFACTS',4)]:
            with patch.object(self.api,constant,count):
                self.api.validate_batch_effect_assessment_pack(FIXTURE/'pack.json')
            for limit in (count-1,0):
                with patch.object(self.api,constant,limit), self.assertRaisesRegex(ValueError,'^input-limit:'):
                    self.api.validate_batch_effect_assessment_pack(FIXTURE/'pack.json')
        largest = max(map(len,records))
        with patch.object(self.api,'MAX_BYTES',largest):
            self.api.validate_batch_effect_assessment_pack(FIXTURE/'pack.json')
        for limit in (largest-1,0):
            with patch.object(self.api,'MAX_BYTES',limit), self.assertRaisesRegex(ValueError,'^input-file:'):
                self.api.validate_batch_effect_assessment_pack(FIXTURE/'pack.json')

    def test_json_string_depth_and_container_limits(self):
        for constant, raw, equal in [('MAX_TEXT',b'{"x":"abcd"}',4),('MAX_DEPTH',b'{"x":{"y":1}}',2),
                                     ('MAX_ITEMS',b'{"x":[1,2]}',2)]:
            with patch.object(self.api,constant,equal):
                self.api._json(raw,self.api.MAX_TOTAL_NODES)
            with patch.object(self.api,constant,equal-1), self.assertRaisesRegex(ValueError,'^[a-z-]+:'):
                self.api._json(raw,self.api.MAX_TOTAL_NODES)
        with self.assertRaisesRegex(ValueError,'^invalid-record:'):
            self.api._number(True,'number')
        self.api._number(0,'number')
        self.api._number(self.api.MAX_NUMBER,'number')
        with self.assertRaisesRegex(ValueError,'^invalid-record:'):
            self.api._number(self.api.MAX_NUMBER*2,'number')

    def test_hardlink_alias_is_read_and_parsed_once(self):
        folder = self.folder()
        os.link(folder/'evidence.json',folder/'alias.json')
        self.pack['study_outputs'].append(dict(self.pack['study_outputs'][0],path='alias.json'))
        self.write(folder,'pack.json',self.pack)
        count = sum((folder/name).stat().st_size for name in ('pack.json','rules.json','matrix.json','evidence.json'))
        original = self.api._json
        with patch.object(self.api,'_json',wraps=original) as parse, patch.object(self.api,'MAX_TOTAL_BYTES',count):
            result = self.api.validate_batch_effect_assessment_pack(folder/'pack.json')
        self.assertEqual(4,parse.call_count)
        self.assertEqual(5,len(result['input_identities']))

    def test_paths_files_and_sparse_oversize_are_refused(self):
        for value in ('../matrix.json','/matrix.json','a/../matrix.json','a//matrix.json',
                      './matrix.json','a\\matrix.json','C:matrix.json','.',[],None):
            folder = self.folder()
            self.pack['inputs']['matrix']['path'] = value
            with self.subTest(value=value), self.assertRaisesRegex(ValueError,'^input-path:|^invalid-record:'):
                self.run_pack(folder)
        self.pack = json.loads((FIXTURE/'pack.json').read_bytes())
        for kind in ('directory','fifo','symlink','oversize'):
            folder = self.folder()
            target = folder/'matrix.json'
            target.unlink()
            if kind == 'directory':
                target.mkdir()
            elif kind == 'fifo':
                os.mkfifo(target)
            elif kind == 'symlink':
                target.symlink_to('rules.json')
            else:
                with target.open('wb') as handle:
                    handle.truncate(self.api.MAX_BYTES+1)
            with self.subTest(kind=kind), self.assertRaisesRegex(ValueError,'^input-file:'):
                self.api.validate_batch_effect_assessment_pack(folder/'pack.json')
        folder = self.folder()
        (folder/'linked').symlink_to('.',target_is_directory=True)
        self.pack['inputs']['matrix']['path'] = 'linked/matrix.json'
        with self.assertRaisesRegex(ValueError,'^input-file:'):
            self.run_pack(folder)

    def test_artifact_replacement_and_growth_are_detected(self):
        folder = self.folder()
        original = self.api.reference_computation
        def change_after(*args):
            result = original(*args)
            target = folder/'matrix.json'
            target.write_bytes(target.read_bytes()+b' ')
            return result
        with patch.object(self.api,'reference_computation',side_effect=change_after), self.assertRaisesRegex(ValueError,'^input-changed:'):
            self.api.validate_batch_effect_assessment_pack(folder/'pack.json')
        folder = self.folder()
        original_fstat = os.fstat
        inode = (folder/'matrix.json').stat().st_ino
        reads = 0
        def grow(descriptor):
            nonlocal reads
            info = original_fstat(descriptor)
            if info.st_ino == inode:
                reads += 1
                if reads == 2:
                    with (folder/'matrix.json').open('ab') as handle:
                        handle.write(b' ')
                    info = original_fstat(descriptor)
            return info
        with patch.object(self.api.os,'fstat',side_effect=grow), self.assertRaisesRegex(ValueError,'^input-changed:'):
            self.api.validate_batch_effect_assessment_pack(folder/'pack.json')

    def test_root_and_transient_ancestor_swaps_are_refused(self):
        for part in ('bundle','parent'):
            folder = self.folder()
            target = folder if part == 'bundle' else folder.parent
            saved = target.with_name(target.name+'-saved')
            original_open = os.open
            changed = False
            def swap(name, flags, *args, **kwargs):
                nonlocal changed
                if name == part and flags & os.O_DIRECTORY and not changed:
                    changed = True
                    target.rename(saved)
                    target.symlink_to(saved.name,target_is_directory=True)
                return original_open(name,flags,*args,**kwargs)
            try:
                with patch.object(self.api.os,'open',side_effect=swap), self.assertRaisesRegex(ValueError,'^input-file:|^input-root:'):
                    self.api.validate_batch_effect_assessment_pack(folder/'pack.json')
            finally:
                if changed:
                    target.unlink()
                    saved.rename(target)
            self.assertTrue(changed)

    def test_parent_swap_preserving_bundle_inode_and_final_root_swap(self):
        for parent_swap in (True,False):
            folder = self.folder()
            original = self.api.reference_computation
            bundle_inode = folder.stat().st_ino
            def swap(*args):
                result = original(*args)
                if parent_swap:
                    parent = folder.parent
                    saved = parent.with_name('saved-parent')
                    parent.rename(saved)
                    parent.mkdir()
                    (saved/folder.name).rename(folder)
                    self.assertEqual(bundle_inode,folder.stat().st_ino)
                else:
                    folder.rename(folder.with_name('saved-bundle'))
                    folder.mkdir()
                return result
            with patch.object(self.api,'reference_computation',side_effect=swap), self.assertRaisesRegex(ValueError,'^input-root:'):
                self.api.validate_batch_effect_assessment_pack(folder/'pack.json')

    def test_rule_freeze_precedes_any_matrix_open(self):
        folder = self.folder()
        self.pack['freeze_before_matrix'] = False
        self.write(folder,'pack.json',self.pack)
        original = os.open
        def guard(name,*args,**kwargs):
            self.assertNotEqual('matrix.json',name)
            return original(name,*args,**kwargs)
        with patch.object(self.api.os,'open',side_effect=guard), self.assertRaisesRegex(ValueError,'^rule-freeze:'):
            self.api.validate_batch_effect_assessment_pack(folder/'pack.json')


if __name__ == '__main__':
    unittest.main()
