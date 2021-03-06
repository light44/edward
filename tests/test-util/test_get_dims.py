from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import tensorflow as tf
import numpy as np

from edward.util import get_dims


class test_get_dims_class(tf.test.TestCase):

  def test_get_dims_0d_tf(self):
    with self.test_session():
      x = tf.constant(0.0)
      self.assertEqual(get_dims(x), [])

  def test_get_dims_0d_np(self):
    with self.test_session():
      x = np.array(0.0)
      self.assertEqual(get_dims(x), [])

  def test_get_dims_1d_tf(self):
    with self.test_session():
      x = tf.zeros([2])
      self.assertEqual(get_dims(x), [2])

  def test_get_dims_1d_np(self):
    with self.test_session():
      x = np.zeros([2])
      self.assertEqual(get_dims(x), [2])

  def test_get_dims_2d_tf(self):
    with self.test_session():
      x = tf.zeros([2, 2])
      self.assertEqual(get_dims(x), [2, 2])

  def test_get_dims_2d_np(self):
    with self.test_session():
      x = np.zeros([2, 2])
      self.assertEqual(get_dims(x), [2, 2])

if __name__ == '__main__':
  tf.test.main()
