from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import numpy as np
import tensorflow as tf

from edward.stats import bernoulli, beta, norm, dirichlet, invgamma, multinomial
from edward.util import cumprod, get_dims, get_session, to_simplex
from itertools import product


class RandomVariable(object):
  """Base class for Edward random variables.

  ``p(x | params) = prod_{idx in shape} p(x[idx] | params[idx])``

  where ``shape`` is the shape of ``x`` and ``params[idx]`` denote the
  parameters of each random variable ``x[idx]``.

  Attributes
  ----------
  shape : tuple of int
    Shape of random variable(s); see below.
  n_vars : int
    The number of variables; equals the product of ``shape``.
  n_params : int
    The number of parameters.
  is_differentiable : bool
    ``True`` if its density is differentiable with respect to its
    input
  is_multivariate : bool
    ``True`` if its distribution is multivariate.
  is_reparameterized : bool
    ``True`` if sampling from ``RandomVariable`` is done by
    reparameterizing random noise drawn from another distribution.
  """
  def __init__(self, shape=1):
    """Initialize.

    Parameters
    ----------
    shape : int, list of int, or tuple of int, optional
      Shape of random variable(s). If ``is_multivariate=True``,
      then the inner-most (right-most) dimension indicates the
      multivariate dimension. Otherwise, all dimensions are
      conceptually the same.
    """
    get_session()
    if isinstance(shape, int):
      shape = (shape, )
    elif isinstance(shape, list):
      shape = tuple(shape)

    self.shape = shape
    self.n_vars = np.prod(self.shape)
    self.n_params = None
    self.is_differentiable = False
    self.is_multivariate = False
    self.is_reparameterized = False

  def sample(self, n=1):
    """Sample from ``RandomVariable``.

    .. math::
      x \sim p(x | \\text{params})

    Parameters
    ----------
    n : int, optional
      Number of samples to return.

    Returns
    -------
    tf.Tensor
      A (n x shape) tensor of type tf.float32, where each
      slice along the first dimension is a sample from p.
    """
    raise NotImplementedError()

  def log_prob(self, xs):
    """Evaluate log probability.

      ``log p(xs | params)``

    Parameters
    ----------
    xs : tf.Tensor
      n x self.shape

    Returns
    -------
    tf.Tensor
      A 1-D tensor for each log density evaluation,

      .. code-block:: none

        [ sum_{idx in shape} log p(xs[1, idx] | params[idx]),
        ...,
        sum_{idx in shape} log p(xs[n, idx] | params[idx]) ]
    """
    # Loop over each random variable.
    # If distribution is univariate, this is over all indices; if
    # distribution is multivariate, this is over all but the last
    # index.
    n = get_dims(xs)[0]
    log_prob = tf.zeros([n], dtype=tf.float32)
    if len(self.shape) == 1:
      if self.is_multivariate:
        idx = ()
        log_prob += self.log_prob_idx(idx, xs)
      else:
        for idx in product(range(self.shape[0])):
          log_prob += self.log_prob_idx(idx, xs)

    elif len(self.shape) == 2:
      if self.is_multivariate:
        for idx in product(range(self.shape[0])):
          log_prob += self.log_prob_idx(idx, xs)

      else:
        for idx in product(range(self.shape[0]), range(self.shape[1])):
          log_prob += self.log_prob_idx(idx, xs)

    elif len(self.shape) == 3:
      if self.is_multivariate:
        for idx in product(range(self.shape[0]), range(self.shape[1])):
          log_prob += self.log_prob_idx(idx, xs)

      else:
        for idx in product(range(self.shape[0]),
                           range(self.shape[1]),
                           range(self.shape[2])):
          log_prob += self.log_prob_idx(idx, xs)

    else:  # len(self.shape) >= 4
      # There should be a generic solution.
      raise NotImplementedError()

    return log_prob

  def log_prob_idx(self, idx, xs):
    """Log probability (single index)

      ``log p(xs[:, idx] | params[idx])``

    Parameters
    ----------
    idx : tuple of int
      Index of the random variable to take the log density of.
      If univariate random variable, idx is of length
      len(self.shape). If multivariate random variable, idx is of
      length len(self.shape[:-1]); note if len(self.shape) is 1
      for multivariate, then idx must be an empty tuple.
    xs : tf.Tensor
      n x self.shape

    Returns
    -------
    tf.Tensor
      A 1-D tensor for each log density evaluation,

      .. code-block:: none

        [ log p(xs[1, idx] | params[idx]),
        ...,
        log p(xs[S, idx] | params[idx]) ]

    Raises
    ------
    NotImplementedError
    """
    raise NotImplementedError()

  def entropy(self):
    """Entropy.

    .. code-block:: none

      H(p(x| params))
      = E_{p(x | params)} [ - log p(x | params) ]
      = sum_{idx in shape} E_{p(x[idx] | params[idx])}
        [ - log p(x[idx] | params[idx]) ]

    Returns
    -------
    tf.Tensor
      A 0-D tensor.
    """
    raise NotImplementedError()


class Bernoulli(RandomVariable):
  """Bernoulli

  See :class:`edward.stats.distributions.Bernoulli`
  """
  def __init__(self, shape=1, p=None):
    super(Bernoulli, self).__init__(shape)
    self.n_params = self.n_vars
    self.is_differentiable = False
    self.is_multivariate = False
    self.is_reparameterized = True

    if p is None:
      p_unconst = tf.Variable(tf.random_normal(self.shape))
      p = tf.sigmoid(p_unconst)

    self.p = p

  def __str__(self):
    p = self.p.eval()
    return "probability: \n" + p.__str__()

  def sample(self, n=1):
    # Reparameterization trick to sample from Bernoulli. This is
    # necessary as sampling from Bernoulli is unavailable in
    # TensorFlow natively.
    eps = tf.random_uniform((n, ) + self.shape)
    return tf.cast(tf.less(eps, self.p), tf.float32)

  def log_prob_idx(self, idx, xs):
    full_idx = (slice(0, None), ) + idx  # slice over sample size
    return bernoulli.logpmf(xs[full_idx], self.p[idx])

  def entropy(self):
    return tf.reduce_sum(bernoulli.entropy(self.p))


class Beta(RandomVariable):
  """Beta

  See :class:`edward.stats.distributions.Beta`
  """
  def __init__(self, shape=1, alpha=None, beta=None):
    super(Beta, self).__init__(shape)
    self.n_params = 2 * self.n_vars
    self.is_differentiable = True
    self.is_multivariate = False
    self.is_reparameterized = False

    if alpha is None:
      alpha_unconst = tf.Variable(tf.random_normal(self.shape))
      alpha = tf.nn.softplus(alpha_unconst)

    if beta is None:
      beta_unconst = tf.Variable(tf.random_normal(self.shape))
      beta = tf.nn.softplus(beta_unconst)

    self.alpha = alpha
    self.beta = beta

  def __str__(self):
    sess = get_session()
    a, b = sess.run([self.alpha, self.beta])
    return "shape: \n" + a.__str__() + "\n" + \
           "scale: \n" + b.__str__()

  def sample(self, n=1):
    # Define Python function which returns samples as a Numpy
    # array. This is necessary for sampling from distributions
    # unavailable in TensorFlow natively.
    def np_sample(a, b):
      # get ``n`` from lexical scoping
      return beta.rvs(a, b, size=n).astype(np.float32)

    x = tf.py_func(np_sample, [self.alpha, self.beta], [tf.float32])[0]
    x.set_shape((n, ) + self.shape)  # set shape from unknown shape
    return x

  def log_prob_idx(self, idx, xs):
    full_idx = (slice(0, None), ) + idx  # slice over sample size
    return beta.logpdf(xs[full_idx], self.alpha[idx], self.beta[idx])

  def entropy(self):
    return tf.reduce_sum(beta.entropy(self.alpha, self.beta))


class Dirichlet(RandomVariable):
  """Dirichlet

  See :class:`edward.stats.distributions.Dirichlet`
  """
  def __init__(self, shape, alpha=None):
    super(Dirichlet, self).__init__(shape)
    self.n_params = self.n_vars
    self.is_differentiable = True
    self.is_multivariate = True
    self.is_reparameterized = False

    if alpha is None:
      alpha_unconst = tf.Variable(tf.random_normal(self.shape))
      alpha = tf.nn.softplus(alpha_unconst)

    self.alpha = alpha

  def __str__(self):
    alpha = self.alpha.eval()
    return "concentration: \n" + alpha.__str__()

  def sample(self, n=1):
    # Define Python function which returns samples as a Numpy
    # array. This is necessary for sampling from distributions
    # unavailable in TensorFlow natively.
    def np_sample(alpha):
      # get ``n`` from lexical scoping
      return dirichlet.rvs(alpha, size=n).astype(np.float32)

    x = tf.py_func(np_sample, [self.alpha], [tf.float32])[0]
    x.set_shape((n, ) + self.shape)  # set shape from unknown shape
    return x

  def log_prob_idx(self, idx, xs):
    """
    ``log p(xs[:, idx, :] | params[idx, :])``
    where ``idx`` is of dimension ``shape[:-1]``
    """
    idx = idx + (slice(0, None), )  # slice over multivariate dimension
    full_idx = (slice(0, None), ) + idx  # slice over sample size
    return dirichlet.logpdf(xs[full_idx], self.alpha[idx])

  def entropy(self):
    return tf.reduce_sum(dirichlet.entropy(self.alpha))


class InvGamma(RandomVariable):
  """Inverse Gamma

  See :class:`edward.stats.distributions.InvGamma`
  """
  def __init__(self, shape=1, alpha=None, beta=None):
    super(InvGamma, self).__init__(shape)
    self.n_params = 2 * self.n_vars
    self.is_differentiable = True
    self.is_multivariate = False
    self.is_reparameterized = False

    if alpha is None:
      alpha_unconst = tf.Variable(tf.random_normal(self.shape))
      alpha = tf.nn.softplus(alpha_unconst) + 1e-2

    if beta is None:
      beta_unconst = tf.Variable(tf.random_normal(self.shape))
      beta = tf.nn.softplus(beta_unconst) + 1e-2

    self.alpha = alpha
    self.beta = beta

  def __str__(self):
    sess = get_session()
    a, b = sess.run([self.alpha, self.beta])
    return "shape: \n" + a.__str__() + "\n" + \
           "scale: \n" + b.__str__()

  def sample(self, n=1):
    # Define Python function which returns samples as a Numpy
    # array. This is necessary for sampling from distributions
    # unavailable in TensorFlow natively.
    def np_sample(a, scale):
      # get ``n`` from lexical scoping
      return invgamma.rvs(a, scale=scale, size=n).astype(np.float32)

    x = tf.py_func(np_sample, [self.alpha, self.beta], [tf.float32])[0]
    x.set_shape((n, ) + self.shape)  # set shape from unknown shape
    return x

  def log_prob_idx(self, idx, xs):
    full_idx = (slice(0, None), ) + idx  # slice over sample size
    return invgamma.logpdf(xs[full_idx], self.alpha[idx], self.beta[idx])

  def entropy(self):
    return tf.reduce_sum(invgamma.entropy(self.alpha, self.beta))


class Multinomial(RandomVariable):
  """Multinomial

  See :class:`edward.stats.distributions.Multinomial`

  ``p(x | params ) = prod_{idx in shape[:-1]} Multinomial(x[idx] | pi[idx])``

  where ``x[idx]`` represents a multivariate random variable, and
  ``params = pi.shape[-1]`` denotes the multivariate dimension.

  Notes
  -----
  For each slice along the last dimension (each multinomial
  distribution), it assumes a single trial (n=1) when sampling and
  calculating the density.
  """
  def __init__(self, shape, pi=None):
    super(Multinomial, self).__init__(shape)
    if self.shape[-1] == 1:
      raise ValueError("Multinomial is not supported for K=1. Use Bernoulli.")

    self.n_params = np.prod(self.shape[:-1]) * (self.shape[-1] - 1)
    self.is_differentiable = False
    self.is_multivariate = True
    self.is_reparameterized = False

    if pi is None:
      real_shape = self.shape[:-1]
      K_minus_one = self.shape[-1] - 1
      pi_unconst = tf.Variable(tf.random_normal([real_shape + (K_minus_one, )]))
      pi = to_simplex(pi_unconst)

    self.pi = pi

  def __str__(self):
    pi = self.pi.eval()
    return "probability: \n" + pi.__str__()

  def sample(self, n=1):
    # Define Python function which returns samples as a Numpy
    # array. This is necessary for sampling from distributions
    # unavailable in TensorFlow natively.
    def np_sample(p):
      # get ``n`` from lexical scoping
      return multinomial.rvs(np.ones(self.shape[:-1]),
                             p, size=n).astype(np.float32)

    x = tf.py_func(np_sample, [self.pi], [tf.float32])[0]
    x.set_shape((n, ) + self.shape)  # set shape from unknown shape
    return x

  def log_prob_idx(self, idx, xs):
    """
    ``log p(xs[:, idx, :] | params[idx, :])``
    where ``idx`` is of dimension ``shape[:-1]``
    """
    idx_K = idx + (slice(0, None), )  # slice over multivariate dimension
    full_idx = (slice(0, None), ) + idx_K  # slice over sample size
    return multinomial.logpmf(xs[full_idx], np.ones(self.shape[:-1])[idx],
                              self.pi[idx_K])

  def entropy(self):
    return tf.reduce_sum(multinomial.entropy(np.ones(self.shape[:-1]), self.pi))


class Normal(RandomVariable):
  """Normal

  See :class:`edward.stats.distributions.Norm`
  """
  def __init__(self, shape=1, loc=None, scale=None):
    super(Normal, self).__init__(shape)
    self.n_params = 2 * self.n_vars
    self.is_differentiable = True
    self.is_multivariate = False
    self.is_reparameterized = True

    if loc is None:
      loc = tf.Variable(tf.random_normal(self.shape))

    if scale is None:
      scale_unconst = tf.Variable(tf.random_normal(self.shape))
      scale = tf.nn.softplus(scale_unconst)

    self.loc = loc
    self.scale = scale

  def __str__(self):
    sess = get_session()
    m, s = sess.run([self.loc, self.scale])
    return "mean: \n" + m.__str__() + "\n" + \
           "std dev: \n" + s.__str__()

  def sample(self, n=1):
    return self.loc + tf.random_normal((n, ) + self.shape) * self.scale

  def log_prob_idx(self, idx, xs):
    full_idx = (slice(0, None), ) + idx  # slice over sample size
    return norm.logpdf(xs[full_idx], self.loc[idx], self.scale[idx])

  def entropy(self):
    return tf.reduce_sum(norm.entropy(scale=self.scale))


class PointMass(RandomVariable):
  """Point mass distribution

  ``p(x | params ) = prod_{idx in shape} Dirac(x[idx] | params[idx])``

  ``Dirac(x; p)`` is the Dirac delta distribution with density equal to
  1 if x == p and 0 otherwise.

  Parameters
  ----------
  params : tf.Tensor, optional
       If not specified, everything initialized to :math:`\mathcal{N}(0,1)`.
  """
  def __init__(self, shape=1, params=None):
    super(PointMass, self).__init__(shape)
    self.n_params = self.n_vars
    self.is_differentiable = False
    self.is_multivariate = False
    self.is_reparameterized = True

    if params is None:
      params = tf.Variable(tf.random_normal(self.shape))

    self.params = params

  def __str__(self):
    if self.params.get_shape()[0] == 0:
      return "parameter values: \n" + "None"

    params = self.params.eval()
    return "parameter values: \n" + params.__str__()

  def sample(self, n=1):
    """Sample from a point mass distribution.

    Each sample is simply the set of point masses, as all
    probability mass is located there.

    Parameters
    ----------
    n: int
      number of samples
    """
    return tf.pack([self.params] * n)

  def log_prob_idx(self, idx, xs):
    """Log probability at an index of a point mass distribution.

    Returns
    -------
    tf.Tensor
      A 1-D tensor where the jth element is 1 if xs[j, idx] is equal
      to params[idx], 0 otherwise.
    """
    full_idx = (slice(0, None), ) + idx  # slice over sample size
    return tf.cast(tf.equal(xs[full_idx], self.params[idx]), dtype=tf.float32)
