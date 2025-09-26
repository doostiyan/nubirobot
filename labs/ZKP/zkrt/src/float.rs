use bellman::gadgets::boolean::AllocatedBit;
use bellman::gadgets::num::AllocatedNum;
use bellman::{ConstraintSystem, LinearCombination, SynthesisError};
use ff::{PrimeField, PrimeFieldBits};

pub struct AllocatedFloat<S: PrimeField + PrimeFieldBits> {
    num: AllocatedNum<S>,
}

pub fn assert_num_bits<S: PrimeField + PrimeFieldBits, CS: ConstraintSystem<S>>(
    cs: &mut CS,
    v: LinearCombination<S>,
    val: Option<S>,
    num_bits: usize,
) -> Result<(), SynthesisError> {
    let mut bits = Vec::new();
    let mut coeff = S::ONE;
    let mut all = LinearCombination::<S>::zero();
    let bit_vals: Option<Vec<bool>> = val.map(|v| v.to_le_bits().iter().map(|b| *b).collect());
    for i in 0..num_bits {
        let bit = AllocatedBit::alloc(&mut *cs, bit_vals.as_ref().map(|b| b[i]))?;
        all = all + (coeff, bit.get_variable());
        bits.push(bit);
        coeff = coeff.double();
    }

    cs.enforce(
        || "check",
        |lc| lc + &all,
        |lc| lc + CS::one(),
        |lc| lc + &v,
    );
    Ok(())
}

impl<S: PrimeField + PrimeFieldBits> AllocatedFloat<S> {
    pub fn alloc<CS: ConstraintSystem<S>>(cs: &mut CS, f: f32) -> Result<Self, SynthesisError> {
        let val = S::from(((f as f64) * 2.0f64.powf(32.0)) as u64);
        let num = AllocatedNum::alloc(&mut *cs, || Ok(val))?;
        cs.enforce(
            || "",
            |lc| lc + num.get_variable(),
            |lc| lc + CS::one(),
            |lc| lc + num.get_variable(),
        );
        let n = Self { num };
        Ok(n)
    }
    pub fn add<CS: ConstraintSystem<S>>(
        &self,
        cs: &mut CS,
        other: &Self,
    ) -> Result<Self, SynthesisError> {
        let val = self
            .num
            .get_value()
            .zip(other.num.get_value())
            .map(|(a, b)| a + b);
        let num = AllocatedNum::alloc(&mut *cs, || val.ok_or(SynthesisError::AssignmentMissing))?;
        cs.enforce(
            || "",
            |lc| lc + self.num.get_variable() + other.num.get_variable(),
            |lc| lc + CS::one(),
            |lc| lc + num.get_variable(),
        );
        Ok(Self { num })
    }
    pub fn sub<CS: ConstraintSystem<S>>(
        &self,
        cs: &mut CS,
        other: &Self,
    ) -> Result<Self, SynthesisError> {
        let val = self
            .num
            .get_value()
            .zip(other.num.get_value())
            .map(|(a, b)| a - b);
        let num = AllocatedNum::alloc(&mut *cs, || val.ok_or(SynthesisError::AssignmentMissing))?;
        cs.enforce(
            || "",
            |lc| lc + self.num.get_variable() - other.num.get_variable(),
            |lc| lc + CS::one(),
            |lc| lc + num.get_variable(),
        );
        Ok(Self { num })
    }
    pub fn mul<CS: ConstraintSystem<S>>(
        &self,
        cs: &mut CS,
        other: &Self,
    ) -> Result<Self, SynthesisError> {
        let mul1 = self.num.mul(&mut *cs, &other.num)?;

        let val = mul1.get_value().map(|v| {
            let as128 =
                u128::from_le_bytes(v.to_repr().as_ref().to_vec()[..16].try_into().unwrap()) >> 32;
            (as128 as u64).into()
        });
        let num = AllocatedNum::alloc(&mut *cs, || val.ok_or(SynthesisError::AssignmentMissing))?;

        assert_num_bits(
            &mut *cs,
            LinearCombination::zero() + mul1.get_variable()
                - ((1u64 << 32).into(), num.get_variable()),
            num.get_value()
                .zip(mul1.get_value())
                .map(|(num, mul1)| mul1 - num * S::from(1u64 << 32)),
            32,
        )?;

        Ok(Self { num })
    }
    pub fn to_string(&self) -> Option<String> {
        if let Some(v) = self.num.get_value() {
            let vv = u64::from_le_bytes(v.to_repr().as_ref().to_vec()[..8].try_into().unwrap());
            let f = (vv as f64) / 2.0f64.powi(32);
            Some(format!("{}", f))
        } else {
            None
        }
    }
}
