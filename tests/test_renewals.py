import unittest
from stormwater.renewals import credit_renewals, history_assessment


class RenewalTests(unittest.TestCase):
    def event(self, **kwargs):
        return {'id':'award-1', 'credit_id':'green-1', 'category':'green_roof',
                'status':'awarded', 'effective_from':'2024-02-29',
                'expires_on':'2028-02-29', 'evidence_refs':[{'source_url':'https://example.test/award'}], **kwargs}

    def test_inclusive_leap_and_lead_boundaries(self):
        for as_of, status, remaining in [('2027-11-30','current',91), ('2027-12-01','upcoming',90),
                                         ('2028-02-29','upcoming',0), ('2028-03-01','overdue',-1)]:
            with self.subTest(as_of=as_of):
                r=credit_renewals([self.event()], as_of)[0]
                self.assertEqual((r['status'],r['days_remaining']), (status,remaining))

    def test_unknown_dates_and_expired_flag_do_not_establish_award_or_term(self):
        for event in [self.event(expires_on=None), self.event(status='expired')]:
            r=credit_renewals([event], '2026-11-15')[0]
            self.assertEqual(r['status'],'unknown_dates')
            self.assertIsNone(r['deadline'])

    def test_renewal_supersedes_expired_award_without_erasing_it(self):
        events=[self.event(expires_on='2026-01-01'), self.event(id='renewal-2',status='renewed',
                supersedes='award-1',effective_from='2026-01-01', expires_on='2030-01-01')]
        r=credit_renewals(events,'2026-11-15')[0]
        self.assertEqual(r['status'],'current')
        self.assertEqual(r['history_ids'],['award-1','renewal-2'])
        events[-1]['expires_on']=None
        self.assertEqual(credit_renewals(events,'2026-11-15')[0]['status'],'unknown_dates')

    def test_termination_applications_and_unknown_termination_dates(self):
        for state, deadline, expected in [('terminated','2026-11-01','terminated'),
                                           ('terminated',None,'unknown_dates'),('applied',None,'not_awarded'),
                                           ('denied',None,'not_awarded')]:
            r=credit_renewals([self.event(status=state,terminated_on=deadline)],'2026-11-15')[0]
            self.assertEqual(r['status'],expected)

    def test_contradictory_dates_sources_and_events_are_explicit(self):
        for events in [[self.event(expires_on='2023-01-01')], [self.event(expires_on='2027-02-29')],
                       [self.event(source_contradiction=True)], [self.event(),self.event(id='other')],
                       [self.event(supersedes='missing')]]:
            self.assertEqual(credit_renewals(events,'2026-11-15')[0]['status'],'contradictory')

    def test_reminder_preferences_are_not_rule_deadlines(self):
        case={'assessment':{'credit_history':[self.event()], 'renewal_lead_days':30}}
        r=history_assessment(case,'2028-01-01')
        self.assertEqual(r['renewals'][0]['status'],'current')
        self.assertIn('not a legal deadline',r['reminder_basis'])
        with self.assertRaises(ValueError):credit_renewals([],lead_days=-1)
