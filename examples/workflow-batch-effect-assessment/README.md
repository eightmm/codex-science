# Synthetic batch-structure fixtures

Every input and expected result here is a redistributable synthetic fixture,
not biological evidence. Run the one-bundle command documented in the pack's
stages reference. The validator writes nothing; concurrent calls leave inputs
unchanged, and a killed call may leave incomplete stdout only.

The balanced fixture has eight synthetic sample columns across two batches and
two biological groups, with two technical replicate labels per group. The first
feature is 0, 2, 4, 6, 2, 4, 6, 8. The second is twice the first plus one. One
additional feature contains null and one is constant; both are excluded under
the frozen named filter without altering the source matrix.

The first feature grand mean is 4. Batch means are 2 and 6, so between sum of
squares is 32 and within sum of squares 16: batch R-squared is 2/3 and F is 12.
Group means are 3 and 5, so between sum of squares is 8 and within sum of squares
40: group R-squared is 1/6 and F is 6/5. Affine scaling of the second feature
preserves those ratios. Batch centroid score is 2/3; group centroid score is 1/10.
The pooled Euclidean batch pseudo-F is 12. The two frozen cross-batch QC samples
have distance 4 times square root of 5; distance SD is zero. With seed 1729 and
199 within-group permutations the plus-one p-value is 0.075. The frozen alpha
0.1, R-squared 0.5 and centroid 0.5 give batch-structure-detected. These permissive
fixture thresholds are not recommendations for real data.

The confounded fixture makes batch equal to biological group. Exact design rank
is 2 for 3 columns, and both groups occur in one batch. It must return
unassessable, with metrics null. It never establishes absent batch structure.

`pack.json` and `confounded.pack.json` name immutable input hashes;
`expected.json` and `confounded.expected.json` freeze expected JSON. The computed
evidence record deliberately cannot support a positive claim. The 27 cases in
`negative-cases.json` each point to a complete mutated synthetic bundle and its
expected labelled finding. Focused tests exercise every case and removal of its
guard must make that individual case fail. Failed controls and unavailable
sources are preserved, never relabelled as negative evidence.
