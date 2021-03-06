from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import numpy as np
import tensorflow as tf

from edward.stats import nbinom
from scipy import stats


class test_nbinom_logpmf_class(tf.test.TestCase):

  def _test(self, x, n, p):
    xtf = tf.constant(x)
    val_true = stats.nbinom.logpmf(x, n, p)
    with self.test_session():
      self.assertAllClose(nbinom.logpmf(xtf, n, p).eval(), val_true)
      self.assertAllClose(nbinom.logpmf(xtf, tf.constant(n),
                                        tf.constant(p)).eval(), val_true)

  def test_int_0d(self):
    self._test(1, 5, 0.5)
    self._test(2, 5, 0.75)

  def test_float_0d(self):
    self._test(1.0, 5, 0.5)
    self._test(2.0, 5, 0.75)

  def test_int_1d(self):
    self._test([1, 5, 3], 5, 0.5)
    self._test([2, 8, 2], 5, 0.75)

  def test_float_1d(self):
    self._test([1.0, 5.0, 3.0], 5, 0.5)
    self._test([2.0, 8.0, 2.0], 5, 0.75)

  def test_int_2d(self):
    self._test(np.array([[1, 5, 3], [2, 8, 2]]), 5, 0.5)
    self._test(np.array([[2, 8, 2], [1, 5, 3]]), 5, 0.75)

  def test_float_2d(self):
    self._test(np.array([[1.0, 5.0, 3.0], [2.0, 8.0, 2.0]]), 5, 0.5)
    self._test(np.array([[2.0, 8.0, 2.0], [1.0, 5.0, 3.0]]), 5, 0.75)
