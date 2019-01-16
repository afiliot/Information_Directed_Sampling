from MAB import *
from copy import copy


class BetaBernoulliMAB(GenericMAB):
    def __init__(self, p):
        super().__init__(method=['B']*len(p), param=p)
        self.Cp = sum([(self.mu_max-x)/self.kl(x, self.mu_max) for x in self.means if x != self.mu_max])
        self.flag = False
        self.optimal_arm = None
        self.threshold = 0.99

    @staticmethod
    def kl(x, y):
        """
        Implementation of the Kullback-Leibler divergence for two Bernoulli distributions (B(x),B(y))
        """
        return x * np.log(x/y) + (1-x) * np.log((1-x)/(1-y))

    def TS(self, T):
        """
        Implementation of the Thomson Sampling algorithm
        :param T: number of rounds
        :return: Reward obtained by the policy and sequence of the chosen arms
        """
        Sa, Na, reward, arm_sequence = self.init_lists(T)
        theta = np.zeros(self.nb_arms)
        for t in range(T):
            for k in range(self.nb_arms):
                if Na[k] >= 1:
                    theta[k] = np.random.beta(Sa[k]+1, Na[k]-Sa[k]+1)
                else:
                    theta[k] = np.random.uniform()
            arm = rd_argmax(theta)
            self.update_lists(t, arm, Sa, Na, reward, arm_sequence)
        return reward, arm_sequence

    def BayesUCB(self, T, p1, p2, c=0):
        """
        BayesUCB implementation in the case of a Beta(p1, p2) prior on the theta parameters
        for a BinomialMAB.
        Implementation of On Bayesian Upper Confidence Bounds for Bandit Problems, Kaufman & al,
        from http://proceedings.mlr.press/v22/kaufmann12/kaufmann12.pdf
        :param T: number of rounds
        :param p1: First parameter of the Beta prior probability distribution
        :param p2: Second parameter of the Beta prior probability distribution
        :param c: Parameter for the quantiles. Default value c=0
        :return: Reward obtained by the policy and sequence of the arms choosed
        """
        Sa, Na, reward, arm_sequence = self.init_lists(T)
        quantiles = np.zeros(self.nb_arms)
        for t in range(T):
            for k in range(self.nb_arms):
                if Na[k] >= 1:
                    quantiles[k] = beta.ppf(1-1/((t+1)*np.log(T)**c), Sa[k] + p1, p2 + Na[k] - Sa[k])
                else:
                    quantiles[k] = beta.ppf(1-1/((t+1)*np.log(T)**c), p1, p2)
            arm = rd_argmax(quantiles)
            self.update_lists(t, arm, Sa, Na, reward, arm_sequence)
        return reward, arm_sequence

    def IR_approx(self, N, b1, b2, X, f, F, G):
        """
        Implementation of the Information Ratio for bernoulli bandits with beta prior
        :param b1: np.array, first parameter of the beta distribution for each arm
        :param b2: np.array, second parameter of the beta distribution for each arm
        :return: the two components of the Information ration delta and g
        """
        assert type(b1) == np.ndarray, "b1 type should be an np.array"
        assert type(b2) == np.ndarray, "b2 type should be an np.array"
        maap = np.zeros((self.nb_arms, self.nb_arms))
        p_star = np.zeros(self.nb_arms)
        prod_F1 = np.ones((self.nb_arms, self.nb_arms, N))
        for a in range(self.nb_arms):
            for ap in range(self.nb_arms):
                for app in range(self.nb_arms):
                    if a != app and app != ap:
                        prod_F1[a, ap] = prod_F1[a, ap]*F[app]
                prod_F1[a, ap] *= f[a]/N
        for a in range(self.nb_arms):
            p_star[a] = (prod_F1[a, a]).sum()
            for ap in range(self.nb_arms):
                if a != ap:
                    maap[ap, a] = (prod_F1[a, ap]*G[ap]).sum()/p_star[a]
                else:
                    maap[a, a] = (prod_F1[a, a]*X).sum()/p_star[a]
        rho_star = np.inner(np.diag(maap), p_star)
        delta = rho_star - b1/(b1+b2)
        g = np.zeros(self.nb_arms)
        for arm in range(self.nb_arms):
            sum_log = maap[arm]*np.log(maap[arm]*(b1+b2)/b1) + (1-maap[arm])*np.log((1-maap[arm])*(b1+b2)/b2)
            g[arm] = np.inner(p_star, sum_log)
        return delta, g, p_star, maap

    @staticmethod
    def fact_list(count):
        l = np.ones(int(count)+1) # add 1 for safety
        for i in range(int(count)):
            l[i+1] = (i+1)*l[i]
        return l

    def init_approx(self, N, beta_1, beta_2):
        """
        :param N: number of points to take in the [0,1] interval
        :param beta_1: prior on alpha for each arm
        :param beta_2: prior on beta for each arm
        :return: Initialisation of the arrays for the approximation of the integrals in IDS
        The initialization is made for uniform prior (equivalent to beta(1,1))
        """
        fact = self.fact_list((beta_1+beta_2).max())
        B = fact[beta_1-1]*fact[beta_2-1]/fact[beta_1+beta_2-1]
        X = np.linspace(1/N, 1., N)
        f = np.array([X**(beta_1[i]-1)*(1.-X)**(beta_2[i]-1)/B[i] for i in range(self.nb_arms)])
        F = (f/N).cumsum(axis=1)
        G = (f*X/N).cumsum(axis=1)
        return X, f, F, G, B

    def update_approx(self, arm, y, beta, X, f, F, G, B):
        """
        Update all functions with recursion formula. These formula are all derived
        using the properties of the beta distribution: the pdf and cdf of beta(a, b)
         can be used to compute the cdf and pdf of beta(a+1, b) and beta(a, b+1)
        """
        adjust = beta[0]*y+beta[1]*(1-y)
        sign_F_update = 1. if y == 0 else -1.
        f[arm] = (X*y+(1-X)*(1-y))*beta.sum()/adjust*f[arm]
        G[arm] = beta[0]/beta.sum()*(F[arm]-X**beta[0]*(1.-X)**beta[1]/beta[0]/B[arm])
        F[arm] = F[arm] + sign_F_update*X**beta[0]*(1.-X)**beta[1]/adjust/B[arm]
        B[arm] = B[arm]*adjust/beta.sum()
        return f, F, G, B

    def IDS_approx(self, T, N_steps, beta1, beta2, display_results = False):
        """
        Implementation of the Information Directed Sampling with approximation of integrals
        :param T: number of rounds
        :return: Reward obtained by the policy and sequence of chosen arms
        """
        beta1, beta2 = copy(beta1), copy(beta2)
        Sa, Na, reward, arm_sequence = self.init_lists(T)
        X, f, F, G, B = self.init_approx(N_steps, beta1, beta2)
        p_star = np.zeros(self.nb_arms)
        for t in range(T):
            if not self.flag:
                if np.max(p_star) > self.threshold:
                    self.flag = True
                    self.optimal_arm = np.argmax(p_star)
                    arm = self.optimal_arm
                else:
                    delta, g, p_star, maap = self.IR_approx(N_steps, beta1, beta2, X, f, F, G)
                    arm = self.IDSAction(delta, g)
            else:
                arm = self.optimal_arm
            self.update_lists(t, arm, Sa, Na, reward, arm_sequence)
            prev_beta = np.array([copy(beta1[arm]), copy(beta2[arm])])
            beta1[arm] += reward[t]
            beta2[arm] += 1-reward[t]
            if display_results:
                print(t)
                print('delta {}'.format(delta))
                print('g {}'.format(g))
                print('ratio : {}'.format(delta**2/g))
                print('p_star {}'.format(p_star))
                print('maap {}'.format(maap))
                print(arm, Na)
                print('mean {}'.format(Sa/Na))
            f, F, G, B = self.update_approx(arm, reward[t], prev_beta, X, f, F, G, B)
        return reward, arm_sequence


    def KG(self, T):
        """
        Implementation of Knowledge Gradient algorithm
        :param T: number of rounds
        :return: Reward obtained by the policy and sequence of the chosen arms
        """
        Sa, Na, reward, arm_sequence = self.init_lists(T)
        v = np.zeros(self.nb_arms)
        for t in range(T):
            if t < self.nb_arms:
                arm = t
            else:
                mu = Sa / Na
                c = np.array([max([mu[i] for i in range(self.nb_arms) if i != arm]) for arm in range(self.nb_arms)])
                for arm in range(self.nb_arms):
                    if mu[arm] <= c[arm] < (Sa[arm]+1)/(Na[arm]+1):
                        v[arm] = mu[arm] * ((Sa[arm]+1)/(Na[arm]+1) - c[arm])
                    elif Sa[arm]/(Na[arm]+1) < c[arm] < mu[arm]:
                        v[arm] = (1-mu[arm])*(c[arm]-Sa[arm]/(Na[arm]+1))
                    else:
                        v[arm] = 0
                arm = rd_argmax(mu + (T-t)*v)
            self.update_lists(t, arm, Sa, Na, reward, arm_sequence)
        return reward, arm_sequence

    def Approx_KG_star(self, T):
        Sa, Na, reward, arm_sequence = self.init_lists(T)
        m = np.zeros(self.nb_arms)
        for t in range(T):
            if t < self.nb_arms:
                arm = t
            else:
                mu = Sa / Na
                c = np.array([max([mu[i] for i in range(self.nb_arms) if i != arm]) for arm in range(self.nb_arms)])
                for arm in range(self.nb_arms):
                    if c[arm] >= mu[arm]:
                        ta = Na[arm] * (c[arm]-mu[arm]) / (1-c[arm]+10e-9)
                        m[arm] = np.nan_to_num(mu[arm]**ta/ta)
                    else:
                        ta = Na[arm] * (mu[arm]-c[arm]) / (c[arm]+10e-9)
                        m[arm] = ((1-mu[arm])**ta)/ta
                arm = rd_argmax(mu + (T-t)*m)
            self.update_lists(t, arm, Sa, Na, reward, arm_sequence)
        return reward, arm_sequence

    def computeIDS(self, Maap, p_a,thetas, M, VIDS=False):
        mu = np.mean(thetas, axis=1)
        theta_hat = np.argmax(thetas, axis=0)
        for a in range(self.nb_arms):
            mu[a] = np.mean(thetas[a])
            for ap in range(self.nb_arms):
                t = thetas[ap, np.where(theta_hat == a)]
                Maap[ap, a] = np.nan_to_num(np.mean(t))
                if ap == a:
                    p_a[a] = t.shape[1]/M
        if np.max(p_a) >= self.threshold:
            self.optimal_arm = np.argmax(p_a)
            arm = self.optimal_arm
        else:
            rho_star = sum([p_a[a] * Maap[a, a] for a in range(self.nb_arms)])
            delta = rho_star - mu
            if VIDS:
                v = np.array([sum([p_a[ap] * (Maap[a, ap] - mu[a]) ** 2 for ap in range(self.nb_arms)]) for a in range(self.nb_arms)])
                arm = rd_argmax(-delta ** 2 / v)
            else:
                g = np.array([sum([p_a[ap] * (Maap[a, ap] * np.log(Maap[a, ap]/mu[a]+1e-10) +
                                              (1-Maap[a, ap]) * np.log((1-Maap[a, ap])/(1-mu[a])+1e-10))
                                   for ap in range(self.nb_arms)]) for a in range(self.nb_arms)])
                arm = self.IDSAction(delta, g)
        return arm, p_a

    def IDS_sample(self, T, M=100000):
        Sa, Na, reward, arm_sequence = self.init_lists(T)
        beta1, beta2 = np.ones(self.nb_arms), np.ones(self.nb_arms)
        reward, arm_sequence = np.zeros(T), np.zeros(T)
        Maap, p_a = np.zeros((self.nb_arms, self.nb_arms)), np.zeros(self.nb_arms)
        thetas = np.array([np.random.beta(beta1[arm], beta2[arm], M) for arm in range(self.nb_arms)])
        for t in range(T):
            if not self.flag:
                if np.max(p_a) >= self.threshold:
                    self.flag = True
                    arm = self.optimal_arm
                else:
                    arm, p_a = self.computeIDS(Maap, p_a, thetas, M)
            else:
                arm = self.optimal_arm
            self.update_lists(t, arm, Sa, Na, reward, arm_sequence)
            beta1[arm] += reward[t]
            beta2[arm] += 1-reward[t]
            thetas[arm] = np.random.beta(beta1[arm], beta2[arm], M)
        return reward, arm_sequence


    def VIDS_sample(self, T, M=100000, VIDS=True):
        Sa, Na, reward, arm_sequence = self.init_lists(T)
        beta1, beta2 = np.ones(self.nb_arms), np.ones(self.nb_arms)
        reward, arm_sequence = np.zeros(T), np.zeros(T)
        Maap, p_a = np.zeros((self.nb_arms, self.nb_arms)), np.zeros(self.nb_arms)
        thetas = np.array([np.random.beta(beta1[arm], beta2[arm], M) for arm in range(self.nb_arms)])
        for t in range(T):
            if not self.flag:
                if np.max(p_a) >= self.threshold:
                    self.flag = True
                    arm = self.optimal_arm
                else:
                    arm, p_a = self.computeIDS(Maap, p_a, thetas, M, VIDS)
            else:
                arm = self.optimal_arm
            self.update_lists(t, arm, Sa, Na, reward, arm_sequence)
            beta1[arm] += reward[t]
            beta2[arm] += 1-reward[t]
            thetas[arm] = np.random.beta(beta1[arm], beta2[arm], M)
        return reward, arm_sequence