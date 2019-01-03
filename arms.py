import numpy as np


class AbstractArm(object):
    def __init__(self, mean, variance, random_state):
        """
        Args:
            mean: expectation of the arm
            variance: variance of the arm
            random_state (int): seed to make experiments reproducible
        """
        self.mean = mean
        self.variance = variance
        self.local_random = np.random.RandomState(random_state)

    def sample(self):
        pass


class ArmBernoulli(AbstractArm):
    def __init__(self, p, random_state=0):
        """
        Bernoulli arm
        Args:
             p (float): mean parameter
             random_state (int): seed to make experiments reproducible
        """
        self.p = p
        super(ArmBernoulli, self).__init__(mean=p,
                                           variance=p * (1. - p),
                                           random_state=random_state)

    def sample(self):
        return self.local_random.rand(1) < self.p


class ArmBeta(AbstractArm):
    def __init__(self, a, b, random_state=0):
        """
        arm having a Beta distribution
        Args:
             a (float): first parameter
             b (float): second parameter
             random_state (int): seed to make experiments reproducible
        """
        self.a = a
        self.b = b
        super(ArmBeta, self).__init__(mean=a/(a + b),
                                      variance=(a * b)/((a + b) ** 2 * (a + b + 1)),
                                      random_state=random_state)

    def sample(self):
        return self.local_random.beta(self.a, self.b, 1)


class ArmGaussian(AbstractArm):
    def __init__(self, mu, eta, random_state=0):
        """
        arm having a Normal distribution
        Args:
             mu (float): mean parameter
             eta (float): std parameter
             random_state (int): seed to make experiments reproducible
        """
        self.mu = mu
        self.eta = eta
        super(ArmGaussian, self).__init__(mean=mu,
                                          variance=eta,
                                          random_state=random_state)

    def sample(self):
        return self.local_random.normal(self.mu, self.eta, 1)


class ArmExp(AbstractArm):
    # https://en.wikipedia.org/wiki/Truncated_distribution
    # https://en.wikipedia.org/wiki/Exponential_distribution
    # http://lagrange.math.siu.edu/Olive/ch4.pdf
    def __init__(self, L, B=1., random_state=0):
        """
        pdf =
        Args:
            L (float): parameter of the exponential distribution
            B (float): upper bound of the distribution (lower is 0)
            random_state (int): seed to make experiments reproducible
        """
        assert B > 0.
        self.L = L
        self.B = B
        v_m = (1. - np.exp(-B*L)*(1. + B*L)) / L
        super(ArmExp, self).__init__(mean=v_m / (1. - np.exp(-L * B)),
                                     variance=None,  # compute it yourself!
                                     random_state=random_state)

    def cdf(self, x):
        def CDF(y):
            return 1. - np.exp(-self.L*y)
        # cdf = lambda y: 1. - np.exp(-self.L*y)
        truncated_cdf = (CDF(x) - CDF(0)) / (CDF(self.B) - CDF(0))
        return truncated_cdf

    def inv_cdf(self, q):
        assert 0 <= q <= 1.
        v = - np.log(1. - (1. - np.exp(- self.L * self.B)) * q) / self.L
        return v

    def sample(self):
        # Inverse transform sampling
        # https://en.wikipedia.org/wiki/Inverse_transform_sampling
        q = self.local_random.random_sample(1)
        x = self.inv_cdf(q=q)
        return x


class ArmFinite(AbstractArm):
    def __init__(self, X, P, random_state=0):
        """
        Arm with finite support
        Args:
            X: support of the distribution (np.array)
            P: associated probabilities (np.array)
            random_state (int): seed to make experiments reproducible
        """
        self.X = X
        self.P = P
        mean = np.sum(X * P)
        super(ArmFinite, self).__init__(mean=mean,
                                        variance=np.sum(X ** 2 * P) - mean ** 2,
                                        random_state=random_state)

    def sample(self):
        """
        Sampling strategy for an arm with a finite support and the associated probability distribution
        :return: A sample from the arm
        """
        i = self.local_random.choice(len(self.P), size=1, p=self.P)
        reward = self.X[i]
        return reward
