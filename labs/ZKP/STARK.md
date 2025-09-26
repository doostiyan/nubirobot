## FRI

### Goal

We have an arbitrary polynomial $P(x)$. We want to prove that $P(x)$ is a polynomial with degree $2^d-1$ without revealing the polynomial.

$P(x) = a_0 + a_1.x + a_2.x^2 + \dots + a_{2^d-1}.x^{2^d-1}$

We need to know some concepts before learning the protocol.

#### Reed-Solomon Coding

Imagine we have a list of $2^n$ numbers $a_0, a_1, \dots, a_{2^n-1}$ (In $\mathbb{F}_p$) that we want to send over a noisy channel. We want the receiver to detect and correct errors in case they happen.

Instead of sending the $2^n$ numbers directly, we build a degree $2^n-1$ polynomial such that:

$P(0) = a_0$

$P(1) = a_1$

$P(2) = a_2$

$\vdots$

$P(2^n-1) = a_{2^n-1}$

Now, we evaluate the polynomial on $4 \times 2^n$ locations and send it to the receiver: $P(0), P(0.25), P(0.5), P(0.75), P(1), P(1.25), \dots, P(2^n-1)$

The receiver will interpolate the polynomial from these $4 \times 2^n$ points, and if the resulting polynomial has degree of $2^n - 1$ there hasn't been any error, but if the resulting polynomial is of degree $4 \times 2^n-1$, then there has been an error.

Reed-Solomon was originally invented for error detection/correction (E.g QR codes), but people have discovered other usecases too :smirk: 

#### Polynomial Commitment Scheme

Remember the points we sent to the receiver when discussing Reed-Solomon Codings? $P(0), P(0.25), P(0.5), P(0.75), P(1), P(1.25), \dots, P(2^n-1)$

Now, imagine we commit to $P(x)$ by creating a merkle-tree of those points, the commitment is the merkle root! Using a merkle-tree to commit to a polynomial is called a Polynomial Commitment Scheme.

#### Odd and even polynomials

$P(x)$ can be represented as sum of *odd* and *even* polynomials: $P(x) = P_e(x^2) + x.P_o(x^2)$, where:

$P_e(x^2) = a_0 + a_2.x^2 + a_4.x^4 + \dots + a_{2^d-2}.x^{2^d-2}$

$P_o(x^2) = a_1 + a_3.x^2 + a_5.x^4 + \dots + a_{2^d-1}.x^{2^d-2}$

Therefore: $P(x) = P_e(x^2) + x.P_o(x^2)$

So, our goal is to prove that $P_e(x^2) + x.P_o(x^2)$ is a degree $2^d-1$ polynomial.

**Fact:** If $P(x)$ is really a degree $2^d-1$ polynomial, then $P_e$ and $P_o$ should be degree $2^{d-1}-1$ polynomials (Just substitute $x^2$ with $x$).

### The Protocol

We use mathematical induction:

**Preposition:** Imagine we, as the prover, have commited to two odd ($P_o$) and even ($P_e$) polynomials (Using a merkle-root) and have successfully proven the verifier that both $P_o$ and $P_e$ polynomials are of degree $2^{d-1}-1$.

**Proof:** Now we only have to prove the verifier that $P(x) = P_e(x^2) + x.P_o(x^2)$, because then, the verifier can conclude that $P(x)$ is a degree $2^d-1$ polynomial. How?

We ask the verifier to send us a random number $g$. We then provide $P(g)$, $P(-g)$, $P_o(g^2)$ and $P_e(g^2)$ along with their merkle-proofs to the verifier.

Verifier checks the merkle-proofs and then checks if: 

 * $P(g) = P_e(g^2) + g.P_o(g^2)$
 * $P(-g) = P_e(g^2) - g.P_o(g^2)$

If the checks pass, then there is high probability that $P(x)$ indeed has degree of $2^d-1$.

#### Making it $O(log(n))$

**Preposition:** Imagine we, as the prover, have commited to a smaller polynomial $P_s$ (Using a merkle-root) and have successfully proven the verifier that $P_s$ is of degree $2^{d-1}-1$, **AND**, $P_s$ is somehow deriven from $P_e$ and $P_o$ (E.g. we let the verifier to choose $r$, and then we set $P_s(x) = P_e(x) + r.P_o(x)$ which is a polynomial of degree $2^{d-1}-1$ itself. We call this procedure ***folding***)

**Proof:** Now we only have to prove the verifier that $P(x) = P_e(x^2) + x.P_o(x^2)$, because then, the verifier can conclude that $P(x)$ is a degree $2^d-1$ polynomial. How?

We ask the verifier to send us a random number $r$. We then provide $P(r)$, $P(-r)$, $P_o(r^2)$ and $P_e(r^2)$ along with their merkle-proofs to the verifier.

Verifier checks the merkle-proofs and then checks if: 

 * $P(r) = P_e(r^2) + rP_o(r^2)$
 * $P(-r) = P_e(r^2) - rP_o(r^2)$

If the checks pass, the
