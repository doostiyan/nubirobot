# Zero Knowledge Proofs for the Rendering Equation

Keyvan Kambakhsh - Nobitex Labs

## Abstract

One of the most powerful usecases of succinct Zero-Knowledge proofs is offloading of heavy computations. Rendering Equation is an embarrasingly parallel algorithm which can be offloaded on many computers, and each computer can take part in the generation of the final image by calculating a few pixels of the final image. In a trustless environment, people can submit invalid pixels resulting in a corrupted final image. This paper discusses ways we can utilize Zero-Knowledge Proofs in order to verify correct calculation of pixels in an efficient manner.

Keywords: Zero Knowledge Proofs, Ray Tracing

## Zero-Knowledge Virtual Machines are not efficient

They are not good, because we don't need to verify correct execution of the whole algorithm steps in order to calculate a pixel. We can "prove" that we have witnesses showing that a computation has been done correctly. E.g. we don't need to do fancy floating-point operations implemented in R1CS in order to calculate the square-root of a number $n$. We can provide a witness $w$ (The square-root) and prove that $w^2=n$.

## Proof of Intersection

In a Ray-Tracing algorithm, rays are initially generated from an eye (A point in the space and its direction), which then intersect with objects in the world. The world is a set of mathematical 3D objects (Spheres, Triangles, Planes and etc). We can store the world objects in a Merkle-Tree. A Proof-of-Intersection then would be a merkle-proof to an object that exist in the world, and and appropriate proof that the ray intersects with that object. As an example, we can prove that the intersection point of a ray $(\vec{P}, \vec{D})$ (Where $P$ is the postion and $D$ is the normalized direction of the ray) with a spehre $(\vec{C},r)$ (Where $\vec{C}$ is the center and $r$ is the radius of the sphere), is $\vec{S}$, by showing that:

1. $S$ is on the ray $(\vec{P}, \vec{D})$
2. Distance between $\vec{S}$ and $\vec{C}$ is equal with $r$.

These can be checked with very few number of constraints:

 - $x \gt 0$
 - $\vec{P} + x\vec{D} = S$
 - $|\vec{SC}|^2 = r^2$


Proof of Intersection is not enough for calculating the value of a pixel. There could be an object between the eye and the target object, preventing light to reach the eye from the target object. Besides a Proof of Intersection to the target object, we should also somehow prove that the ray intersects no other objects in the middle of the way.

## Proof of Non-Intersection

We can also prove that a point does not intersect with an object. Example of Proof-of-Non-Intersection for a 3D sphere:

 - $x \gt 0$
 - $\vec{P} + x\vec{D} = S$
 - $|\vec{PS}|^2 = |\vec{PC}|^2 $
 - $|\vec{SC}|^2 \gt r^2$

Now imagine we provide a Proof-of-Intersection and a series of Proof-of-Non-Intersections, showing that there is no object in the middle of the way. Then we can reason about the final color of the pixel.

## Merkle Bounding Volume Hierarchies

In a naive procedure, one needs to generate Proof-of-Non-Intersections for all of the objects in the scene which is inefficient. There is are tree-like data structures named Bounding Volume Hierarchies which split the 3D space into subspaces, and put objects in the subspaces in a nested, tree-like structure, which help the rendering engines find the intersecting object faster ($(O(logn))$ time). We can integrate the idea behind a BVH and Merkle-Trees and provide efficient proofs, that will Proof-of-Non-Intersection for an entire subspace (Which contains many 3D primitive) in a single proof.

## Implementation

As a Proof-of-Concept implementation, we write a ray-tracer from scratch, which only supports rendering of simple spheres and checkerboard planes, and provides a succinct proof for each pixel using the Groth16 zkSNARKs protocol.
