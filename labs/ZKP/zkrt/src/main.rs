mod float;
use float::AllocatedFloat;

use bellman::gadgets::num::AllocatedNum;
use bellman::groth16::{
    create_random_proof, generate_random_parameters, prepare_verifying_key, verify_proof,
};
use bellman::{Circuit, ConstraintSystem, SynthesisError};
use bls12_381::Bls12;
use ff::{PrimeField, PrimeFieldBits};
use rand::thread_rng;

fn hash<S: PrimeField, CS: ConstraintSystem<S>>(
    cs: &mut CS,
    a: &AllocatedNum<S>,
    b: &AllocatedNum<S>,
) -> Result<AllocatedNum<S>, SynthesisError> {
    a.mul(cs, b)
}

fn check_proof<S: PrimeField, CS: ConstraintSystem<S>>(
    cs: &mut CS,
    value: &AllocatedNum<S>,
    proof: &[AllocatedNum<S>],
    root: &AllocatedNum<S>,
    _index: AllocatedNum<S>,
) -> Result<(), SynthesisError> {
    let mut curr = value.clone();
    for p in proof.iter() {
        curr = curr.mul(&mut *cs, p)?;
    }
    cs.enforce(
        || "",
        |lc| lc + root.get_variable(),
        |lc| lc + CS::one(),
        |lc| lc + curr.get_variable(),
    );
    Ok(())
}

#[derive(Debug, Clone, Copy, Default)]
pub struct Point {
    x: f32,
    y: f32,
    z: f32,
}

impl Point {
    fn new(x: f32, y: f32, z: f32) -> Self {
        Self { x, y, z }
    }
    fn zero() -> Point {
        Self {
            x: 0.0,
            y: 0.0,
            z: 0.0,
        }
    }
    fn up() -> Point {
        Self {
            x: 0.0,
            y: 1.0,
            z: 0.0,
        }
    }
    fn norm(&self) -> Self {
        let l = 1.0 / self.len();
        *self * l
    }
    fn len(&self) -> f32 {
        self.dot(*self).sqrt()
    }
    fn dot(&self, other: Self) -> f32 {
        self.x * other.x + self.y * other.y + self.z * other.z
    }
    fn cross(&self, other: Self) -> Self {
        Self {
            x: self.y * other.z - self.z * other.y,
            y: self.z * other.x - self.x * other.z,
            z: self.x * other.y - self.y * other.x,
        }
    }
}
use std::ops::*;

impl Add for Point {
    type Output = Self;
    fn add(self, other: Self) -> Self {
        Self {
            x: self.x + other.x,
            y: self.y + other.y,
            z: self.z + other.z,
        }
    }
}
impl Sub for Point {
    type Output = Self;
    fn sub(self, other: Self) -> Self {
        Self {
            x: self.x - other.x,
            y: self.y - other.y,
            z: self.z - other.z,
        }
    }
}

impl Mul<f32> for Point {
    type Output = Self;
    fn mul(self, other: f32) -> Self {
        Self {
            x: self.x * other,
            y: self.y * other,
            z: self.z * other,
        }
    }
}

struct AllocatedVec<S: PrimeField + PrimeFieldBits> {
    x: AllocatedFloat<S>,
    y: AllocatedFloat<S>,
    z: AllocatedFloat<S>,
}
impl<S: PrimeField + PrimeFieldBits> AllocatedVec<S> {
    fn alloc<CS: ConstraintSystem<S>>(cs: &mut CS, p: Point) -> Result<Self, SynthesisError> {
        Ok(Self {
            x: AllocatedFloat::alloc(&mut *cs, p.x)?,
            y: AllocatedFloat::alloc(&mut *cs, p.y)?,
            z: AllocatedFloat::alloc(&mut *cs, p.z)?,
        })
    }
    fn add<CS: ConstraintSystem<S>>(
        &self,
        cs: &mut CS,
        other: &Self,
    ) -> Result<Self, SynthesisError> {
        Ok(AllocatedVec {
            x: self.x.add(&mut *cs, &other.x)?,
            y: self.y.add(&mut *cs, &other.y)?,
            z: self.z.add(&mut *cs, &other.z)?,
        })
    }
    fn sub<CS: ConstraintSystem<S>>(
        &self,
        cs: &mut CS,
        other: &Self,
    ) -> Result<Self, SynthesisError> {
        Ok(AllocatedVec {
            x: self.x.sub(&mut *cs, &other.x)?,
            y: self.y.sub(&mut *cs, &other.y)?,
            z: self.z.sub(&mut *cs, &other.z)?,
        })
    }
    fn mul<CS: ConstraintSystem<S>>(
        &self,
        cs: &mut CS,
        coeff: &AllocatedFloat<S>,
    ) -> Result<Self, SynthesisError> {
        Ok(AllocatedVec {
            x: self.x.mul(&mut *cs, coeff)?,
            y: self.y.mul(&mut *cs, coeff)?,
            z: self.z.mul(&mut *cs, coeff)?,
        })
    }
}

#[derive(Debug, Default, Clone)]
pub struct RayTracer {
    pub ray: Ray,
    pub collision: Option<f32>,
    pub sphere: Sphere,
    pub color: Point,
}

impl<S: PrimeField + PrimeFieldBits> Circuit<S> for RayTracer {
    fn synthesize<CS: ConstraintSystem<S>>(self, cs: &mut CS) -> Result<(), SynthesisError> {
        let sphere_center = AllocatedVec::alloc(&mut *cs, self.sphere.center)?;
        let _sphere_radius = AllocatedFloat::alloc(&mut *cs, self.sphere.radius)?;
        let ray_pos = AllocatedVec::alloc(&mut *cs, self.ray.pos)?;
        let ray_dir = AllocatedVec::alloc(&mut *cs, self.ray.dir)?;
        let f = AllocatedFloat::alloc(&mut *cs, self.collision.unwrap_or_default())?;

        let mul = ray_dir.mul(&mut *cs, &f)?;
        let isect = ray_pos.add(&mut *cs, &mul)?;
        let delta = sphere_center.sub(&mut *cs, &ray_pos)?;

        let delta_x2 = delta.x.mul(&mut *cs, &delta.x)?;
        let delta_y2 = delta.y.mul(&mut *cs, &delta.y)?;
        let delta_z2 = delta.z.mul(&mut *cs, &delta.z)?;

        let mut dist = delta_x2.add(&mut *cs, &delta_y2)?;
        dist = dist.add(&mut *cs, &delta_z2)?;

        if self.collision.is_some() {
            println!(
                "{:?} {:?} {:?}",
                isect.x.to_string(),
                isect.y.to_string(),
                isect.z.to_string()
            );
        }

        Ok(())
    }
}

use std::io::Write;
fn write_img(data: Vec<Vec<Point>>) -> std::io::Result<()> {
    let w = data[0].len();
    let h = data.len();
    let mut file = std::fs::OpenOptions::new()
        .create(true)
        .write(true)
        .open("out.ppm")?;

    file.write_all(format!("P6 {} {} 255\n", w, h).as_bytes())?;
    for row in data.iter() {
        for pix in row.iter() {
            file.write_all(&[
                (pix.x * 255.0) as u8,
                (pix.y * 255.0) as u8,
                (pix.z * 255.0) as u8,
            ])?;
        }
    }
    Ok(())
}

#[derive(Debug, Clone, Default)]
pub struct Ray {
    pos: Point,
    dir: Point,
}

#[derive(Debug, Clone, Default)]
pub struct Sphere {
    center: Point,
    radius: f32,
}

impl Sphere {
    fn intersects(&self, ray: &Ray) -> Option<f32> {
        let center_sub_pos = self.center - ray.pos;
        let tca = center_sub_pos.dot(ray.dir);
        if tca < 0.0 {
            return None;
        }
        let d2 = center_sub_pos.dot(center_sub_pos) - tca * tca;
        if d2 > self.radius * self.radius {
            return None;
        }
        let thc = (self.radius * self.radius - d2).sqrt();
        let ret = f32::min(tca - thc, tca + thc);
        if ret < 0.0 {
            return None;
        } else {
            return Some(ret);
        }
    }
}

fn main() {
    let width = 20;
    let height = 20;

    let cam = Point {
        x: 0.0,
        y: 50.0,
        z: -100.0,
    };
    let lookat = Point::zero();
    let dir = (lookat - cam).norm();
    let center = cam + dir;
    let right_v = Point::up().cross(dir).norm();
    let up_v = dir.cross(right_v).norm();

    let mut rng = thread_rng();
    let params = {
        let c = RayTracer::default();

        generate_random_parameters::<Bls12, _, _>(c, &mut rng).unwrap()
    };
    let pvk = prepare_verifying_key(&params.vk);

    let s1 = Sphere {
        center: Point::new(0.0, 30.0, 0.0),
        radius: 30.0,
    };

    let s2 = Sphere {
        center: Point::new(0.0, -1000000.0, 0.0),
        radius: 1000000.0,
    };

    let mut data = vec![vec![Point::zero(); width]; height];
    for y_i in 0..height {
        for x_i in 0..width {
            let x = ((x_i as i32 - width as i32 / 2) as f32) / width as f32 * 2.0;
            let y = ((y_i as i32 - height as i32 / 2) as f32) / height as f32 * 2.0;
            let ray_dir = ((center + right_v * x + up_v * y) - cam).norm();
            let ray = Ray {
                pos: cam,
                dir: ray_dir,
            };
            let _isect = s2.intersects(&ray);

            /*if let Some(s) = isect {
                let pos = cam + ray_dir * s;
                if ((pos.x / 20.0).floor() + (pos.z / 20.0).floor()) as i32 % 2 == 0 {
                    data[height - y_i - 1][x_i] = [0.1, 0.1, 0.1];
                } else {
                    data[height - y_i - 1][x_i] = [0.9, 0.9, 0.9];
                }
            }*/

            let isect_s1 = s1.intersects(&ray);
            let expected_color = if isect_s1.is_some() {
                Point::new(1.0, 1.0, 0.0)
            } else {
                Point::zero()
            };

            data[height - y_i - 1][x_i] = expected_color;

            let c = RayTracer {
                sphere: s1.clone(),
                ray: ray.clone(),
                collision: isect_s1,
                color: expected_color.clone(),
            };

            println!("Proving pixel ({}, {})", x_i, y_i);
            let proof = create_random_proof(c, &params, &mut rng).unwrap();
            let inputs = [];
            assert!(verify_proof(&pvk, &proof, &inputs).is_ok());
            //let
        }
    }

    write_img(data).unwrap();
}
