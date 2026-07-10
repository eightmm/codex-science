# Textbook Sources

This registry records the open texts consulted for Codex-native mathematics and
physics skills. The PDFs and extracted text are local study cache only under
`.cache/textbooks/`; they are intentionally excluded from Git.

The authored skills are independent procedural syntheses. They do not copy textbook
prose, figures, worked examples, or exercise sets. Source licenses remain authoritative
for the source books and are not replaced by this repository's license.

## Selection policy

- Use author-, institution-, or recognized open-textbook-hosted copies.
- Require an explicit public-domain, CC BY, CC BY-SA, or similarly modifiable license.
- Record the exact downloaded artifact and SHA-256 digest.
- Exclude sources that prohibit LLM ingestion or allow reading but not downloading.
- Keep source PDFs and extracted text out of the plugin and Git history.
- Re-check terms before refreshing a source; a current website policy may differ from
  the license embedded in an older file.

## Cached sources

### Jiří Lebl — Basic Analysis I

- Scope: proof discipline, real analysis, limits, continuity, fixed points.
- Canonical page: <https://www.jirka.org/ra/>
- Download: <https://www.jirka.org/ra/realanal.pdf>
- Cached artifact: `.cache/textbooks/lebl-basic-analysis-i.pdf`
- Edition: 6.3, May 15, 2026.
- License: dual CC BY-SA 4.0 / CC BY-NC-SA 4.0; this project relies on the
  CC BY-SA option stated in the book.
- SHA-256: `9c204ae1f1ee1641fa604a6456c0d13db4390db44633ee2df9c9d97b5486b7a6`

### Jiří Lebl — Notes on Diffy Qs

- Scope: ODE classification, systems, Fourier series, PDEs, eigenvalue problems,
  Laplace transforms, nonlinear dynamics.
- Canonical page: <https://www.jirka.org/diffyqs/>
- Download: <https://www.jirka.org/diffyqs/diffyqs.pdf>
- Cached artifact: `.cache/textbooks/lebl-diffyqs.pdf`
- Edition: 6.11, 2026.
- License: dual CC BY-SA 4.0 / CC BY-NC-SA 4.0; this project relies on the
  CC BY-SA option stated in the book.
- SHA-256: `0676c6d9f060b06fb62e15d3b3da1af584d84e73e4b8a42d89ade8a7ad91f07b`

### Jim Hefferon — Linear Algebra

- Scope: linear systems, vector spaces, maps, determinants, eigenstructure,
  proof-oriented linear algebra.
- Canonical page: <https://hefferon.net/linearalgebra/>
- Downloaded mirror: <https://upload.wikimedia.org/wikipedia/commons/a/a3/Jim_Hefferon_-_Linear_Algebra_%284th_Edition%29.pdf>
- Cached artifact: `.cache/textbooks/hefferon-linear-algebra.pdf`
- Edition: fourth edition, April 26, 2020.
- License: GFDL 1.2+ and CC BY 3.0 US as recorded on the file page.
- SHA-256: `5240f2782e645bc6351ad9eba69d8c19500142a5cca9c90450c17b3765a1a400`

### Leon Q. Brin — Tea Time Numerical Analysis

- Scope: numerical error, root finding, interpolation, numerical calculus,
  and numerical ODEs.
- Canonical page: <https://sourceforge.net/p/teatimenumericalanalysis/wiki/Home/>
- Download: <https://sourceforge.net/projects/teatimenumericalanalysis/files/pdf/TeaTimeNumericalAnalysis.pdf/download>
- Cached artifact: `.cache/textbooks/brin-tea-time-numerical-analysis.pdf`
- License: CC BY-SA as declared by the project page.
- SHA-256: `61bcd25d4509a958c37b092d5290e4085711aba4050b95f2f176c8c3501bff6e`

### Jeffrey W. Schnick — Calculus-Based Physics I

- Scope: mechanics, conservation laws, rotation, oscillations, waves, and fluids.
- Canonical page: <https://www.cbphysics.org/downloadsI.html>
- Download: <https://www.cbphysics.org/downloadsI/cbphysicsIa18.pdf>
- Cached artifact: `.cache/textbooks/schnick-calculus-physics-i.pdf`
- Revision: August 28, 2008.
- License: CC BY-SA 3.0 as printed in the PDF.
- SHA-256: `8ac9de195dcd414fab9114a4e2363b6c8b72d28ecd4bb34de82b4126ab12c0ae`

### Jeffrey W. Schnick — Calculus-Based Physics II

- Scope: electrostatics, circuits, magnetism, induction, Maxwell equations,
  electromagnetic waves, and optics.
- Canonical page: <https://www.cbphysics.org/downloadsII.html>
- Download: <https://www.cbphysics.org/downloadsII/cbPhysicsIIb24.pdf>
- Cached artifact: `.cache/textbooks/schnick-calculus-physics-ii.pdf`
- Revision: March 12, 2008.
- License: CC BY-SA 2.5 as printed in the PDF.
- SHA-256: `25d52706f70dfc57870b3cbd35f194bd804874e3e5171a03b96a08aa8fdec321`

### Benjamin Crowell — Modern Physics

- Scope: waves, relativity, thermodynamics, statistical reasoning, optics,
  atoms, quantum mechanics, and angular momentum.
- Canonical collection: <https://www.lightandmatter.com/books.html>
- Archived author upload: <https://archive.org/details/mod_20220102>
- Download: <https://archive.org/download/mod_20220102/mod.pdf>
- Cached artifact: `.cache/textbooks/crowell-modern-physics.pdf`
- Revision: October 7, 2021.
- License: CC BY-SA 3.0 for author-created material, with separate third-party
  image credits as printed in the PDF. No images are reused by the skills.
- SHA-256: `e81eb59a63f84068d63132a456032c3905b2a483b962b61be22d7cf1226bd813`

### Benjamin Crowell — General Relativity

- Scope: spacetime conventions, curvature, geodesics, field equations, and
  invariant checks.
- Canonical page: <https://www.lightandmatter.com/genrel/>
- Download: <https://www.lightandmatter.com/genrel/genrel.pdf>
- Cached artifact: `.cache/textbooks/crowell-general-relativity.pdf`
- License: CC BY-SA as printed in the PDF for the author's text and illustrations.
- SHA-256: `f8d9b9affbf8a3ee55089c60acdacf3e74a9d67e61f88e81e2e32c93ca09ad78`

### Barry N. Taylor and Chris E. Kuyatt — NIST Technical Note 1297

- Scope: Type A and Type B evaluation, combined standard uncertainty,
  expanded uncertainty, and measurement-result reporting.
- Canonical page: <https://www.nist.gov/pml/nist-technical-note-1297>
- Download: <https://nvlpubs.nist.gov/nistpubs/legacy/tn/nbstechnicalnote1297.pdf>
- Cached artifact: `.cache/textbooks/nist-tn-1297.pdf`
- Edition: 1994 edition.
- Rights: official United States government publication; consult the NIST
  rights notice before redistributing any incorporated third-party material.
- SHA-256: `f2c8e6026d5589a63d492f192b72cd905f554b477a6049532256170aec477e92`

### Kirisits et al. — Regularization of Nonlinear Inverse Problems

- Scope: functional-analytic inverse problems, variational regularization,
  learned methods, convergence, and uncertainty.
- Canonical record: <https://arxiv.org/abs/2506.17465>
- Download: <https://arxiv.org/pdf/2506.17465>
- Cached artifact: `.cache/textbooks/nonlinear-inverse-problems-regularization.pdf`
- Revision: arXiv v1, June 20, 2025.
- License: the manuscript states a CC BY public copyright license for its
  author-accepted version.
- SHA-256: `e03d60042034fdcffb2276bd926755ae682d10fdcea59e21557781a684272ead`

### Taha Sochi — Tensor Calculus Made Simple

- Scope: tensor notation, coordinate transformation, covariant calculus,
  metrics, connections, and curvature.
- Canonical record: <https://figshare.com/articles/book/Tensor_Calculus_Made_Simple/26983177>
- Download: <https://ndownloader.figshare.com/files/49116076>
- Cached artifact: `.cache/textbooks/sochi-tensor-calculus-made-simple.pdf`
- Published: October 18, 2024.
- License: CC BY 4.0 as recorded by Figshare.
- SHA-256: `8aaa3ab3cd4c4555c746e392314f8f2d038d4644639c79b42274962f1a073a7b`

## Consulted web references

These official or openly licensed references informed narrow workflows but are
linked rather than copied into the repository. They do not replace primary
literature, current standards, or tool documentation for a concrete project.

- Kyle Siegrist, *Probability, Mathematical Statistics, and Stochastic Processes*,
  CC BY 4.0: <https://commons.libretexts.org/book/stats-10114>
- OpenIntro, *Introduction to Modern Statistics*, with the project license:
  <https://www.openintro.org/book/ims/> and <https://www.openintro.org/license/>
- Howard Seltman, *Experimental Design and Analysis*, CC BY-NC 4.0:
  <https://repository.iit.edu/islandora/object/islandora%3A1012018>
- OpenLearn, *Introduction to the Calculus of Variations*, CC BY-NC:
  <https://www.open.edu/openlearn/science-maths-technology/introduction-the-calculus-variations/content-section-0>
- Michael Hitchman, *Geometry with an Introduction to Cosmic Topology*,
  CC BY-SA: <https://textbooks.aimath.org/textbooks/approved-textbooks/hitchman/>
- Wikimedia, *Control Systems*, CC BY-SA 3.0:
  <https://commons.wikimedia.org/wiki/File:Control_Systems.pdf>
- Official *Theorem Proving in Lean 4* documentation:
  <https://docs.lean-lang.org/theorem_proving_in_lean4/>
- NASA, verification, validation, and uncertainty-quantification guidance:
  <https://ntrs.nasa.gov/citations/20070017454>

## Explicit exclusions

- OpenStax: current pages explicitly prohibit unapproved LLM training or ingestion.
  Do not download or ingest OpenStax content for skill authoring without permission.
- Feynman Lectures online edition: free to read online but explicitly does not grant
  a right to download the text. Do not cache or transform it.
- Commercial textbook mirrors: never use unofficial copies regardless of technical
  availability.

## Skills grounded in this registry

- `mathematical-problem-execution`
- `proof-and-counterexample`
- `linear-algebra-problem-solving`
- `ode-pde-solving`
- `numerical-analysis-error-control`
- `dimensional-analysis-units`
- `classical-mechanics`
- `electromagnetism`
- `thermodynamics-statistical-mechanics`
- `quantum-mechanics`
- `probability-stochastic-processes`
- `statistical-inference-experimental-design`
- `optimization-variational-methods`
- `asymptotic-perturbation-methods`
- `complex-fourier-analysis`
- `experimental-uncertainty-propagation`
- `continuum-mechanics`
- `relativity-spacetime`
- `computational-physics-validation`
- `control-dynamical-systems`
- `geometry-topology`
- `formal-theorem-proving`
- `optics-wave-physics`
- `condensed-matter-solid-state`
- `nuclear-particle-physics`
- `inverse-problems-regularization`
- `chaos-nonlinear-dynamics`
- `tensor-calculus-differential-geometry`
