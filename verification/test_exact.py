import unittest
from verification.exact import verify


class ExactTest(unittest.TestCase):
    def test_original_equation_rejects_extraneous_root(self):
        result=verify({'kind':'substitute','left':'sqrt(x+6)','right':'x','values':['3','-2']})
        self.assertEqual(result['status'],'failed')
        self.assertTrue(result['checks'][0]['passed'])
        self.assertFalse(result['checks'][1]['passed'])

    def test_polynomial_identity_exact(self):
        self.assertEqual(verify({'kind':'polynomial_identity','left':'(x-3)**2','right':'x**2-6*x+9'})['status'],'passed')

    def test_does_not_cancel_rational_domain(self):
        self.assertEqual(verify({'kind':'polynomial_identity','left':'(x**2-1)/(x-1)','right':'x+1'})['status'],'error')

    def test_code_execution_disallowed(self):
        for left in ('__import__("os").system("id")','x.__class__','[x for x in [1]]','2**10000','open("/tmp/test")'):
            self.assertEqual(verify({'kind':'substitute','left':left,'right':'0','values':['1']})['status'],'error')

    def test_zero_denominator_not_passed(self):
        self.assertEqual(verify({'kind':'substitute','left':'1/(x-1)','right':'0','values':['1']})['status'],'failed')

    def test_nonreal_value_not_passed(self):
        self.assertEqual(verify({'kind':'substitute','left':'sqrt(x)','right':'1','values':['-1']})['status'],'failed')

    def test_cancellation_does_not_erase_undefined_point(self):
        self.assertEqual(verify({'kind':'substitute','left':'(x-1)/(x-1)','right':'1','values':['1']})['status'],'failed')
        self.assertEqual(verify({'kind':'polynomial_identity','left':'(x-1)/(x-1)','right':'1'})['status'],'error')

    def test_squaring_cannot_erase_real_sqrt_domain(self):
        self.assertEqual(verify({'kind':'substitute','left':'sqrt(x)**2','right':'x','values':['-1']})['status'],'failed')
        self.assertEqual(verify({'kind':'polynomial_identity','left':'sqrt(x)**2','right':'x'})['status'],'error')

    def test_zero_times_log_does_not_erase_domain(self):
        self.assertEqual(verify({'kind':'substitute','left':'0*log(x)','right':'0','values':['0']})['status'],'failed')

    def test_decimal_literals_are_not_rounded_to_binary_float(self):
        self.assertEqual(verify({'kind':'substitute','left':'1.0000000000000001','right':'1','values':['0']})['status'],'failed')
        self.assertEqual(verify({'kind':'substitute','left':'0.1+0.2','right':'0.3','values':['0']})['status'],'passed')

    def test_nested_numeric_power_bounded(self):
        self.assertEqual(verify({'kind':'substitute','left':'(((10**20)**20)**20)','right':'0','values':['0']})['status'],'error')


if __name__=='__main__':unittest.main()
