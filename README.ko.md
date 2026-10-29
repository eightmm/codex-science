<p align="center">
  <img src="assets/codex-science-banner.svg" alt="Codex Science" width="100%">
</p>

<p align="center">
  <a href="README.md">English</a> ·
  <a href="docs/SETUP.md">설치</a> ·
  <a href="docs/">문서</a>
</p>

<p align="center">
  <a href="https://github.com/eightmm/codex-science/actions/workflows/ci.yml"><img src="https://github.com/eightmm/codex-science/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
</p>

Codex Science는 Codex 작업에서 선택적으로 사용하는 과학 워크벤치입니다.
Claude Science의 공개 workflow에서 영감을 받은 독립 plugin이며, 비공개 구현과의
동등성을 주장하지 않습니다.

- 감사된 스킬 카탈로그 284개: K-Dense-AI 149개, Codex-native 132개,
  DeepMind 인프라 포인터 3개.
- 읽기 전용 공개 데이터 source contract 49개와 카탈로그 검색·연구 계획. 성숙도는 source별로 다르며, 모두 live-tested된 것은 아닙니다.
- 독립 evidence review가 포함된 재현 가능한 실행 artifact.
- 승인 gate를 거치는 로컬·원격 과학 컴퓨팅.

## 빠른 시작

한 번 설치하면 모든 프로젝트에서 사용할 수 있습니다:

```bash
curl -fsSL https://raw.githubusercontent.com/eightmm/codex-science/main/scripts/install.sh | bash
```

설치에는 `curl`, Codex CLI, Git, 그리고 `uv` 또는 Python 3.11 이상이 필요합니다.
`uv`를 사용하면 관리형 Python 3.12 runtime을 기록합니다. Python 3.8 시스템에서는
먼저 `uv`를 설치하세요. Runtime은 표준 라이브러리만 사용합니다. 자세한 내용은
[설치 문서](docs/SETUP.md)를 참고하세요.

관리 대상 checkout은 `~/.codex-science`이며 설치는 사용자 전체에 적용됩니다.

새 Codex 작업에서 `/hooks`를 열고 `SessionStart`, `UserPromptSubmit`, `Stop`
hook을 한 번 신뢰 처리하세요. 이는 사람이 plugin command를 확인하는 보안
경계이며, 시작 문구를 입력해야 science mode가 활성화됩니다. Hook 신뢰는 정확한
bootstrap 정의에 묶여 있으므로, 그 정의가 바뀔 때만 `/hooks`를 다시 검토하면
됩니다. Hook script를 Codex에게 직접 실행하라고 요청하는 것은 hook 신뢰를
대신하지 않습니다.

```text
Start Codex Science
Codex Science 시작
```

명시적으로 종료하려면 `Stop Codex Science` 또는 `Codex Science 종료`를 입력합니다.

기존 설치에서 host bootstrap을 바꿔야 한다면 모든 Codex 작업과 앱을 닫은 뒤
아래 migration 명령을 사용합니다:

```bash
curl -fsSL https://raw.githubusercontent.com/eightmm/codex-science/main/scripts/install.sh | CODEX_SCIENCE_MIGRATION_ACK=all-codex-tasks-closed bash
```

Codex가 열린 상태에서는 확인 값을 사용하지 마세요. migration 뒤의 일반
runtime 업데이트에는 이 명령이 필요하지 않습니다.

## 사용법

활성화는 명시적으로 이뤄집니다. 새 작업에서 일반적인 과학 질문을 해도 mode가
**활성화되지 않습니다**. Codex에는 핵심 스킬 3개만 등록되며, 카탈로그 wrapper는
활성 coordinator가 선택할 때만 로드됩니다.

같은 작업에서 다음과 같이 이어서 요청할 수 있습니다:

```text
이 가설에 관한 최신 1차 문헌을 찾아줘.
가설을 반증할 수 있는 가장 작은 실험을 설계해줘.
결과를 분석하고 재현 가능한 artifact로 기록해줘.
최종 주장을 실행 기록과 대조해 검토해줘.
```

에이전틱 생명과학 예시:

```text
FinnGen, BioBank Japan, UKB/TOPMed에서 rs7903146과 2형 당뇨의 연관성을 비교해줘.
천식 locus의 후보 유전자를 genetics, eQTL, expression, pathway evidence로 우선순위화해줘.
가설에 맞는 공개 proteomics·microbiome dataset을 찾아 study design 적합도로 순위를 매겨줘.
```

대화형 작업은 턴마다 진행합니다. 여러 자동 continuation이 필요하면 새
작업에서 native `/goal`과 구체적인 완료 계약을 사용하세요:

```text
Codex Science 시작.
목표: 제공된 결과를 재현하고 검토된 보고서를 작성한다.
제약: 공개 source와 로컬 CPU만 사용하고 package를 설치하지 않는다.
완료 조건: 테스트 통과, 모든 주장에 저장된 evidence, 독립 review 통과.
```

Goal 실행은 완료되거나, 실제로 막히거나, 승인 gate에 도달할 때까지 계속됩니다.
필수적이지 않은 선호는 기본값을 선택하고, 알려진 결정은 한 번의 질문으로 묶어
묻습니다. Codex가 checkpoint를 자동 생성하므로 사용자가 science_checkpoint.py
명령을 직접 실행할 필요는 없습니다. Checkpoint에는 제어 metadata만 담깁니다.
prompt, credential, 비공개 데이터, 결론은 포함되지 않습니다.

결과는 `artifacts/<run-id>/`에 저장되며 `checkpoint.json`과 로컬 `index.md`를
포함합니다. 요청하면 offline `index.html`도 생성합니다. 주요 이미지는 대화에
표시하고, 보고서·표·notebook·로그·보조 figure는 클릭 가능한 링크로 제공합니다.
웹 배포는 필요하지 않습니다. 독립 review는 기록된 evidence를 검토합니다. 새 방법
개발과 설명되지 않는 연구 병목은 [Research Discovery
Loop](docs/RESEARCH_DISCOVERY.md)를 참고하세요. 이 루프의 CPU fixture는 일반적인
연구 성과를 입증하지 않습니다. [PheWAS acceptance run](examples/life-science-reviewed-run/)
에서 제한된 생명과학 workflow 사례를 볼 수 있습니다.

## 과학 컴퓨터 활용과 승인

로컬 Python, R, Julia, Jupyter, CPU·GPU, 기존 SSH host와 Slurm cluster를
사용할 수 있습니다. 원격 compute에는 cloud GPU 계정과 private object store도
포함됩니다. GUI·브라우저 desktop 자동화는 이 workflow의 범위 밖입니다. 읽기
전용 점검과 기존 환경의 소규모 작업은 바로 진행할 수 있고, 승인된 되돌릴 수 있는
단계는 반복 확인 없이 계속됩니다. Package 설치, 새 host 접속, private data 전송,
원격 job 제출, 유료 자원 사용에는 target, data 이동, 자원, 시간·비용 상한, output
경로와 취소 계획을 적은 승인 packet이 필요합니다. Credential은 실행 artifact에
저장하지 않습니다. 명령, 환경, job ID, 로그, 종료 상태, 비용, output hash는
`artifacts/<run-id>/`에 기록합니다. 자세한 내용은 [과학 컴퓨팅](docs/COMPUTE.md)을
참고하세요.

## 업데이트

Codex를 실행하기 전에 `CODEX_SCIENCE_AUTO_UPDATE`를 설정합니다:

| Mode | 작업 시작 / 최초 활성화 | 명시적 업데이트 |
| --- | --- | --- |
| `apply` (기본값) | 호환 runtime 검증·설치 | 새 활성화에 설치, 진행 중 run은 pin 유지 |
| `notify` | 알림만 표시 | 새 활성화에 설치, 진행 중 run은 pin 유지 |
| `off` | 확인 생략 | 새 활성화에 설치, 진행 중 run은 pin 유지 |

어느 mode에서나 `Codex Science 업데이트` 또는 `Update Codex Science`로
요청할 수 있습니다. 검증 실패 시 last-known-good runtime을 유지합니다. Host
bootstrap migration이나 repair가 안내된 경우에만 curl migration을 실행하세요.
활성 run은 runtime pin을 유지하므로 설치된 runtime을 적용하려면 새 작업을
엽니다. 분류와 runtime identity는 [설치 문서](docs/SETUP.md)를 참고하세요.

## 확인과 문제 해결

`codex plugin list`에서 plugin 상태가 `installed, enabled`인지 확인하세요.
활성화되지 않으면 새 작업에서 `/hooks`를 열어 hook 세 개를 신뢰하고
`Start Codex Science`라고 입력합니다.

### 알려진 제한

Codex 앱이나 작업을 닫으면 Codex Science는 **백그라운드에서 실행되지
않습니다**. Stop hook은 [openai/codex#20783](https://github.com/openai/codex/issues/20783)
때문에 경고만 하고 중단시키지 않습니다. `CODEX_SCIENCE_STOP_MODE=block`은
설치된 Codex에 upstream 수정이 포함된 뒤에만 호환성 시험용으로 유지됩니다.
openai/codex#20783이 재현되는 동안에는 켜지 마세요. 다른 Stop loop와 함께
사용하지 마세요. 세 hook을
모두 신뢰하지 않으면 같은 작업의 지속은 best effort입니다. `waiting_external`은
재개 방법을 기록하지만 작업이 닫힌 동안 polling하지 않습니다.

## 카탈로그와 데이터 출처

카탈로그는 K-Dense-AI 149개, Codex-native 132개, DeepMind 인프라 포인터
3개의 세 tier로 구성됩니다. Codex-native 스킬은 Google DeepMind 과학 스킬
세트, 교재 기반 수학·물리, 통계적 의사결정 분석, 생명과학 근거 종합,
분광학·분석화학, 과학 컴퓨팅, 그리고 ESMFold2, AlphaFold3, RFdiffusion,
BindCraft 같은 현재의 공개 모델을 위한 승인 gate 실행 workflow를 다룹니다.
각 스킬은 active/inactive로 감사됩니다. Inactive 스킬은 감사 사유를 보여 주며,
upstream 지침을 열람하려면 먼저 확인(acknowledgement)이 필요합니다. 읽기 전용
MCP는 `science_search_*`와 `science_plan_*`를 제공하며,
`scripts/science_tool.py`로도 같은 기능을 사용할 수 있습니다. [생명과학 source
지원표](docs/LIFE_SCIENCE_RESEARCH_SOURCES.md)를 참고하세요. 카탈로그에 있다는
사실만으로 실행 권한이 생기지는 않습니다.

## 평가 현황

고정된 6개 문헌 작업 benchmark의 최신 기록인 Run40은 6개 중 5개를 완료했습니다
(95% Wilson 구간 43.6%-97.0%). full-protein-folding은 1800초에 timeout됐고,
policy 차단·provider capacity 실패·재실행은 없었습니다. 과거 Run30은 6개 중
5개를 완료했으며 standard-mrna는 provider policy 차단으로 중단됐습니다. 실행당
작업이 6개뿐이므로 이 결과로 추세를 입증할 수 없습니다. 실행별 근거와 한계는
[평가 문서](docs/EVALUATION.md)에 있습니다.

## 개발

```bash
git clone https://github.com/eightmm/codex-science.git
cd codex-science
./scripts/bootstrap.sh
./scripts/check.sh fast    # offline unit, catalog, plugin, and skill validation
./scripts/doctor.sh        # checkout, submodule, catalog, and environment diagnosis
./scripts/check.sh public  # optional live public-source smoke test
```

`doctor.sh`는 native source와 생성된 wrapper, 고정된 source 무결성을
검증합니다.

개발 checkout을 Codex marketplace로 등록하지 마세요. 실제 plugin은 위 curl
명령으로 설치하고, 이 checkout에서 `codex plugin marketplace add "$PWD"`를
실행하지 마세요.

## 라이선스

Codex Science의 원본 코드는 [MIT License](LICENSE)로 배포됩니다. 가져오거나
각색한 스킬은 upstream 라이선스를 유지합니다. K-Dense-AI 스킬은 개별
라이선스를 따르고, Google DeepMind 스킬은 Apache-2.0 및 CC-BY-4.0 attribution을
유지하며, upstream 라이선스 기록은 고정된 vendor 사본에 보존됩니다. 공개 교재와 분석화학 표준의 출처·라이선스는 [교재 출처](docs/TEXTBOOK_SOURCES.md)와
[분석화학 출처](docs/ANALYTICAL_SOURCES.md)에 기록되어 있습니다. 저장소 수준
파일은 개별 스킬이나 의존성의 라이선스를 덮어쓰지 않습니다.
