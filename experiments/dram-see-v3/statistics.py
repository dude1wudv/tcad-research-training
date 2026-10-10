"""Frozen v3 descriptive intervals with planned denominators and explicit unknowns."""
import math

Z95 = 1.959963984540054
STATUSES = ('correct', 'criterion_error', 'critical', 'numerically_uncertain', 'failed', 'missing')


def wilson(k, n, z=Z95):
    if type(k) is not int or type(n) is not int or n <= 0 or not 0 <= k <= n:
        raise ValueError('Wilson requires integer 0<=k<=N, N>0')
    if z != Z95:
        raise ValueError('v3 intervals use the frozen two-sided 95% z')
    p = k / n
    denominator = 1 + z * z / n
    center = (p + z * z / (2 * n)) / denominator
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denominator
    return [0. if k == 0 else max(0., center - half),
            1. if k == n else min(1., center + half)]


def zero_upper(n):
    if type(n) is not int or n <= 0:
        raise ValueError('Positive integer planned N required')
    return 1 - .05 ** (1 / n)


def summarize_classes(classes, planned_n=4):
    """One bit/condition/threshold; no paired-bit pooling or available-case N."""
    if type(planned_n) is not int or planned_n != 4:
        raise ValueError('The frozen per-stratum planned denominator is 4')
    classes = list(classes)
    if len(classes) > planned_n or any(value not in STATUSES for value in classes):
        raise ValueError('Duplicate/excess responses or unknown outcome status')
    counts = {status: classes.count(status) for status in STATUSES}
    counts['missing'] += planned_n - len(classes)
    unresolved = sum(counts[k] for k in ('critical', 'numerically_uncertain', 'failed', 'missing'))
    errors = counts['criterion_error']
    return {
        'planned_n': planned_n,
        'valid': sum(counts[k] for k in ('correct', 'criterion_error', 'critical')),
        **counts, 'unresolved': unresolved,
        'point_bounds': [errors / planned_n, (errors + unresolved) / planned_n],
        'wilson_95_envelope': [wilson(errors, planned_n)[0], wilson(errors + unresolved, planned_n)[1]],
        'wilson_95_best_assignment': wilson(errors, planned_n),
        'wilson_95_worst_assignment': wilson(errors + unresolved, planned_n),
        'zero_error_exact_one_sided_95_upper': zero_upper(planned_n) if not unresolved and not errors else None,
        'all_planned_determinate': not unresolved,
        'scope': 'Descriptive per-stratum interval; no simultaneous-coverage claim; paired bits do not double N',
    }


def classification(margin_mV, threshold_mV):
    if not math.isfinite(margin_mV) or threshold_mV not in (2.5, 5., 10.):
        raise ValueError('Nonfinite margin or unfrozen threshold')
    return 'correct' if margin_mV > threshold_mV else 'criterion_error' if margin_mV < -threshold_mV else 'critical'


def summarize_matrix(design, outcomes):
    """Use only declared main responses. Missing rows are explicit missing slots.

    Outcome: event_label, stored_bit, status ('measured', failed, missing,
    numerically_uncertain), M_mV when measured, and optional
    numerically_uncertain_thresholds_mV. Process variants/repeats are not samples.
    """
    if design.get('statistics', {}).get('planned_n_each') != 4:
        raise ValueError('Unfrozen statistical design')
    expected = {(event['label'], bit): event for event in design['events'] for bit in (0, 1)}
    indexed = {}
    for outcome in outcomes:
        key = (outcome['event_label'], outcome['stored_bit'])
        if key not in expected or key in indexed:
            raise ValueError('Unknown or duplicate main response; cannot add paired/process repeats')
        if outcome.get('oxide_nm', 5) != 5 or outcome.get('mesh_scale', 1) != 1 or outcome.get('step_scale', 1) != 1:
            raise ValueError('Process/refinement response cannot enlarge the main denominator')
        indexed[key] = outcome
    strata = []
    conditions = sorted({event['condition_id'] for event in design['events']})
    for condition in conditions:
        events = sorted((event for event in design['events'] if event['condition_id'] == condition), key=lambda e: e['replicate'])
        if len(events) != 4 or {event['replicate'] for event in events} != {1, 2, 3, 4}:
            raise ValueError('Expected four distinct predeclared events per physical condition')
        for bit in (0, 1):
            for threshold in design['thresholds_mV']:
                classes = []
                for event in events:
                    row = indexed.get((event['label'], bit))
                    if row is None:
                        classes.append('missing')
                        continue
                    status = row.get('status')
                    if status in ('failed', 'missing', 'numerically_uncertain'):
                        classes.append(status)
                    elif status == 'measured':
                        raw_class = classification(row['M_mV'], threshold)
                        uncertain = row.get('numerically_uncertain_thresholds_mV', [])
                        if any(epsilon not in design['thresholds_mV'] for epsilon in uncertain):
                            raise ValueError('Unknown numerical uncertainty threshold')
                        classes.append('numerically_uncertain' if threshold in uncertain else raw_class)
                    else:
                        raise ValueError('Unknown response validity status')
                strata.append({'condition_id': condition, 'gate_length_um': events[0]['gate_length_um'],
                               'particle': events[0]['particle'], 'angle_deg': events[0]['angle_deg'],
                               'stored_bit': bit, 'threshold_mV': threshold,
                               'event_labels': [event['label'] for event in events],
                               'outcomes': classes, **summarize_classes(classes)})
    return {'schema': 'dram-see-v3-statistics', 'independent_events_planned': len(design['events']),
            'paired_responses_planned': len(expected), 'strata': strata}
