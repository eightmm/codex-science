# User-facing messages

Use this guide when reporting Codex Science progress or results to a person.
Messages should sound like a colleague explaining what the evidence shows and
what they will do next.

## Progress messages

- Write in the user's language. If the user writes Korean, respond in Korean.
- Start with the finding, decision, approval needed, or changed plan.
- Follow with the next action when there is one.
- Send a message only at a meaningful moment: first useful finding, plan change,
  approval request, plan-changing failure, or completion.
- Use one short paragraph or at most three bullets. A bold headline is optional.
- Do not narrate setup, repeat prior updates, or report routine tool activity.
- Keep machine output and full logs intact, but do not paste them into progress
  messages.
- Replace internal names with their human meaning or leave them out.

### Good examples

**English**

> The two data sources agree that the signal is strongest in older samples. I’m
> checking whether that pattern remains after accounting for batch differences.

**Korean**

> 두 자료원 모두 고령 표본에서 신호가 가장 강하다는 점을 보여줍니다.
> 배치 차이를 고려한 뒤에도 이 경향이 유지되는지 확인하겠습니다.

### Bad examples

**English**

> Codex Science is active. The standard tier created a bundle, deterministic
> validation passed, and claim checks are running through the OMS harness.

**Korean**

> 세션 키로 체크포인트를 만들었고 sidecar와 receipt를 생성했습니다.
> 다음 단계는 manifest 검증입니다.

These examples center product setup and internal plumbing instead of useful
scientific information.

## Completion messages

1. Lead with the scientific answer in one to three sentences.
2. List key findings as bullets. Cite each finding that rests on published sources with a visible persistent identifier (DOI, PMID, PMCID, or arXiv ID). When a finding rests on public database or dataset records, name the record identifiers it rests on (the study or dataset accession and, for specific variants, genes or proteins, their identifiers) and the source release or access date when recorded; link computation-only findings to the saved output instead.
3. State caveats that affect interpretation or generalization.
4. Link to the human summary (`index.md`) and the main output files.

Do not answer with a raw JSON object unless the host explicitly requires an
output schema. When it does, write the `summary` field as a readable,
sentence-level answer and preserve the required schema.

### Example

The intervention was associated with a modest reduction in symptom scores in
this study, but the evidence does not establish that it caused the reduction.

- The intervention group had lower average scores at week 8 ([study results](https://example.org/study)).
- The difference was smaller after adjustment for baseline severity ([analysis details](https://example.org/analysis)).

This was one small, short-term study; the result may not generalize to other
populations or settings.

Read the [human summary](../../../artifacts/run-123/index.md) and the [main results table](../../../artifacts/run-123/results.csv).

## Glossary

| Internal term | Plain English | 쉬운 한국어 |
| --- | --- | --- |
| tier | level of review and documentation | 검토와 기록의 수준 |
| checkpoint | saved progress that supports continuing the work | 작업을 이어갈 수 있도록 저장한 진행 내용 |
| hook or session hook | automatic support provided by the app during a task | 작업 중 앱이 자동으로 제공하는 기능 |
| Stop warning | a notice that the task is about to end | 작업이 곧 끝난다는 알림 |
| bundle | the files produced for one research run | 한 번의 연구 작업에서 나온 파일 모음 |
| sidecar | a supporting file that accompanies a result | 결과를 보충하는 파일 |
| manifest | a list describing the files and their contents | 파일과 내용을 정리한 목록 |
| receipt | a record that a review or check took place | 검토나 확인을 했다는 기록 |
| deterministic validation | a repeatable check of structure and values | 구조와 값을 같은 방식으로 확인하는 검사 |
| claim check | a check that a conclusion is supported by evidence | 결론이 근거로 뒷받침되는지 확인 |
| OMS harness | shared agent coordination tools | 에이전트 간 협업 도구 |
| registered claim | a conclusion listed for evidence tracking | 근거 추적 목록에 등록된 결론 |
| schema | the required structure of machine-readable data | 기계가 읽는 데이터의 형식 |
| hash | a fingerprint used to detect file changes | 파일 변경을 감지하는 지문값 |
| counter or issue ID | internal tracking information | 내부 추적 번호 |

Use the plain wording only when it accurately describes what happened. If the
internal term has no useful user-facing equivalent, omit it.

## Links

- Use clickable Markdown links with readable labels that explain the destination.
- For workspace files in chat, use clickable absolute paths when the host needs
  them; inside this guide and other documents, use relative paths where possible.
- Link directly to the human summary and the main results. Do not make users
  interpret a raw path, hash, or file identifier.
- Link citations to the source supporting the specific finding. Do not imply a
  citation supports a broader claim than it does.
