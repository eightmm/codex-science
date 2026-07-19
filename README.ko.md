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

Codex Science는 하나의 Codex 작업을 옵트인 방식의 과학 워크벤치로 바꿉니다: 한 번 시작하면 이후 턴에서 연구 워크플로가 이어지고, 명시적으로 종료합니다. [K-Dense-AI](https://github.com/K-Dense-AI/scientific-agent-skills)에서 pin한 149개에, [Google DeepMind](https://github.com/google-deepmind/science-skills) 과학 스킬 전체, 공개 교재 기반 수학·물리 워크플로 28개, 에이전틱 생명과학 evidence synthesis, 실험 분광·분석화학, 로컬·원격 과학 컴퓨팅, Claude Science 공개 featured workflow, ESMFold2·ESMC·AlphaFold3·Protenix-v2·SimpleFold·RoseTTAFold All-Atom·RFdiffusion·BindCraft 같은 최신 공개 모델의 [Codex-native 저작본](authored-skills/)을 더한 **280개 감사된 에이전트 스킬** 카탈로그로 작업을 라우팅합니다. 공개 source 34개와 로컬 catalog 검색·research planner를 read-only MCP로 제공합니다.

Claude Science의 공개 워크플로에서 영감을 받은 독립 Codex 플러그인이며, 비공개 구현과의 동등성을 주장하지 않습니다.

## 설치

**한 번만** 설치하면 Codex에 전역 등록되어 이후 모든 프로젝트에서 쓸 수 있습니다:

```bash
curl -fsSL https://raw.githubusercontent.com/eightmm/codex-science/main/scripts/install.sh | bash
```

`curl`, Codex CLI, Git, Python 3.11+가 필요합니다(런타임은 순수 Python 표준
라이브러리이므로 패키지·가상환경·`uv` 없이 실행). 설치 스크립트는
`~/.codex-science`에 clone하고 플러그인을 전역 등록한 뒤 런타임 self-check까지
수행하며, 업데이트하려면 다시 실행하면 됩니다.
최초 설치는 staging에서 검증한 뒤 활성화하며, 설치 스크립트를 다시 실행할 때도 hook과 같은 잠금·transactional updater를 사용합니다.
관리 대상 checkout만 실제 설치 source로 사용합니다. 과거 개발 checkout이
`codex-science` marketplace 이름으로 등록되어 있으면 installer가 이를
`~/.codex-science`로 교체하며, 새 source 추가가 실패하면 기존 source를 복구합니다.

그다음 **아무** 프로젝트에서나 새 Codex 작업을 시작하고 `/hooks`를 열어 Codex Science의 `SessionStart`·`UserPromptSubmit`·`Stop` hook을 한 번 신뢰 처리하세요. `Start Codex Science`(또는 `Codex Science 시작`)라고 하면 이후 턴에서는 coordinator가 스스로 재호출됩니다. 프로젝트마다 재설치하지 않습니다.

`Stop` hook도 함께 신뢰 처리해야 합니다. 진행 중인 run의 저장된 다음 행동을
표시합니다. 같은 턴을 강제로 이어 가는 blocking 동작은 현재 기본적으로 꺼져
있습니다. 공개 Codex 버그 [openai/codex#20783](https://github.com/openai/codex/issues/20783)이
hook이 만든 로컬 UUID를 API message ID로 보내 다음 요청을 깨뜨릴 수 있기
때문입니다. Hook 정의가 바뀌는 update 뒤에는 `/hooks`에서 Codex Science hook을
다시 검토하고 신뢰해야 합니다.

`/hooks`는 사람이 확인하는 보안 경계입니다. Plugin command를 승인할 뿐
science mode를 시작하지는 않으므로, 이 승인은 사용자가 직접 처리하는 것이
맞습니다. 신뢰 처리 뒤에는 평문 시작 문구로 mode가 활성화됩니다. Codex에게
hook script를 직접 실행하라고 요청할 필요가 없으며, 직접 실행은 hook 신뢰를
대체하지도 않습니다.

<details>
<summary>개발 checkout</summary>

```bash
git clone https://github.com/eightmm/codex-science.git
cd codex-science
./scripts/bootstrap.sh
./scripts/check.sh fast
```

개발 checkout을 Codex marketplace로 등록하지 마세요. 이 경로는 편집과 검증에만
사용하고, 실제 실행 plugin은 위 curl 명령으로 설치하여 Codex가 항상 관리 대상
`~/.codex-science` checkout을 읽도록 합니다.

</details>

## 사용법

새 작업에서 한 번만 시작합니다 (영어/한국어):

```text
Start Codex Science
Codex Science 시작
```

이후 턴에서는 스킬을 다시 언급하지 않고 그대로 진행합니다:

```text
이 가설에 대한 최신 1차 문헌을 찾아줘.
이 가설을 반증할 수 있는 가장 작은 실험을 설계해줘.
이 결과를 분석하고 재현 가능한 artifact로 기록해줘.
최종 주장을 실행 기록과 대조해 검토해줘.
```

### 실행 모드 선택

대화형 작업은 일반 활성화를 사용합니다. 세 hook을 신뢰하고 같은 작업에서
`Codex Science 시작`을 한 번 말한 뒤 그대로 작업을 이어갑니다.

여러 자동 continuation이 필요한 결과 중심 작업은 native Goal mode를 사용합니다.
새 작업에서 `/goal`을 열고 다음처럼 구체적인 계약을 입력합니다:

```text
Codex Science 시작.
목표: 제공된 결과를 재현하고 검토된 보고서를 작성한다.
제약: 공개 source와 로컬 CPU만 사용하고 package를 설치하지 않는다.
완료 조건: 테스트가 통과하고 모든 주장에 저장된 evidence가 있으며 독립 review가 통과한다.
```

Checkpoint 생성과 CLI 조작은 Codex가 자동으로 수행하므로 사용자가
`science_checkpoint.py` 명령을 입력할 필요가 없습니다. Goal mode는 바깥 작업
lifecycle을, checkpoint는 복원 가능한 과학 실행 기록을 담당합니다.

비단순 작업은 목표를 한 번 요청하면 충분합니다. Codex Science가
`artifacts/<run-id>/checkpoint.json`을 만들고 discovery, 실행, 분석, provenance,
review를 완료할 때까지 이어갑니다. 진짜 blocker나 승인 gate에서만 멈추며,
진행에 영향이 없는 선호는 합리적인 기본값을 선택하고 필요한 결정은 한 번에
묶어 질문합니다. Checkpoint에는 복원용 control metadata만 저장하며 prompt,
credential, private data, conclusion은 저장하지 않습니다.

비단순 checkpoint는 현재 활성화의 owner key와 결합됩니다. `Stop` hook은
`active` run의 저장된 `next_action`을 경고로 보여 주되 턴 종료를 허용하고,
checkpoint는 다음 prompt, resume, 또는 native Goal continuation을 위해 그대로
남깁니다. Hook이 조기 종료를 구제할 것이라고 기대하면 안 됩니다. Coordinator는
현재 턴에서 계속 진행하고 같은 단계의 실질적인 진전 뒤에는 `heartbeat`를
기록해야 합니다. `approval_required`, `waiting_external`, `blocked`는 명시적 중지
상태이며, `waiting_external`은 원격 job을 바쁘게 반복 조회하지 않고 poll 간격과
종료 규칙을 기록합니다.

`CODEX_SCIENCE_STOP_MODE=block`은 설치된 Codex에 상류 수정이 포함된 뒤 호환성
시험을 할 때만 과거 blocking 경로를 되살립니다. openai/codex#20783이 재현되는
동안에는 켜지 마세요. 이 opt-in mode에서만 무진전 3회 안전 탈출,
`CODEX_SCIENCE_MAX_IDLE_CONTINUATIONS=1..20`, run당 기본 100회 절대 continuation
예산이 blocking continuation에 적용됩니다.

Codex Science는 Codex 앱이나 작업을 닫은 뒤 **백그라운드에서 실행되지
않습니다**. Hook 신뢰, permission prompt, 승인 gate, host availability도 우회할
수 없습니다. `waiting_external`은 안전한 재개 방법을 기록할 뿐, 작업이 닫힌
동안 계속 polling하지 않습니다.

Native Goal mode에서도 hook은 Goal tool을 호출하거나 상태를 관찰할 수 없으므로
자동 continuation마다 coordinator가 둘을 연결합니다. 완료 순서는 엄격합니다.
Schema v4 criteria를 run 내부 evidence로 모두 충족하고 독립성이 명시된 review를
통과한 뒤 `completion_pending`에 진입하고 native Goal을 완료해, 해시된 run 내부
완료 영수증을 저장합니다. 이것은 coordinator 내부 절차이며 사용자가 별도 명령을
입력할 필요는 없습니다. 영수증은 감사 가능한 agent evidence이며 hook이 host나
reviewer 신원을 인증하는 것은 아닙니다. 별도의 generic 또는 Ralph식 `Stop` loop를
함께 켜지 마세요. 서로 다른 guard가 종료를 방해할 수 있습니다.

에이전틱 생명과학 사용 예시:

```text
rs7903146과 2형 당뇨의 연관성을 FinnGen, BioBank Japan, UKB/TOPMed에서 비교해줘.
이 천식 locus의 후보 유전자를 genetics, eQTL, expression, pathway evidence로 우선순위화해줘.
이 가설에 맞는 공개 proteomics·microbiome dataset을 찾고 study design 적합도로 순위를 매겨줘.
```

먼저 identifier를 정규화하고 필요한 evidence lane만 조회한 뒤 source release와
정확한 query를 기록하고, 충돌을 조정해 독립 review까지 수행합니다.
[에이전틱 생명과학 source 지원표](docs/LIFE_SCIENCE_RESEARCH_SOURCES.md)를 참고하세요.
체크인된 [PheWAS acceptance run](examples/life-science-reviewed-run/)은 제한된
라이브 조회, 고정 evidence snapshot, 보수적인 genome-build 처리, 결정적 분석,
artifact hash와 review를 함께 보여줍니다. 공개 API drift 검사는 주 1회 및 수동
실행 전용 workflow로 분리되어 일시적인 외부 장애가 pull-request CI를 막지 않습니다.
Reactome은 현재 GitHub-hosted runner IP에 HTTP 403을 반환하므로 scheduled run에서
해당 environment block만 명시적으로 보고합니다. 다른 source/status 실패는 그대로
실패하며, 로컬 `scripts/check.sh public`은 모든 source에 대해 엄격하게 동작합니다.

활성 상태는 Codex의 `session_id`와 private marker에 저장된 무작위 generation에
연결됩니다. Raw session ID, prompt, 연구 데이터는 저장하지 않습니다. 둘에서
파생한 owner key는 하나의 nonterminal checkpoint를 해당 활성화에만 묶으므로 다른
작업이나 나중 활성화가 Stop guard를 물려받지 않습니다. Resume과 context
compaction에서는 generation을 유지합니다. 명시적 종료나 `clear`는 발견 가능한
소유 nonterminal run을 `abandoned`로 만들고 marker를 지우며, 다음 활성화는 새
generation과 owner key를 생성합니다. Artifact를 찾을 수 없는 경우에도 generation
회전이 과거 run의 guard 재획득을 막습니다. Activation marker는 180일 동안
사용되지 않으면 만료됩니다.
`SessionStart`, `UserPromptSubmit`, `Stop` hook을 모두 신뢰하지 않았다면 같은 작업의
대화 문맥을 통한 best-effort 지속만 가능하며 resume/compaction context와 active
checkpoint 경고는 보장되지 않습니다.

명시적으로 종료합니다:

```text
Stop Codex Science
Codex Science 종료
```

## 자동 업데이트

기본 `notify` mode는 새 Codex Science 작업을 시작할 때 공식 GitHub `main`
branch를 최대 24시간에 한 번 확인합니다. 새 버전이 있으면 평문으로
설치합니다:

```text
Codex Science 업데이트
Update Codex Science
```

관리 대상 `~/.codex-science` checkout은 변경사항이 없어야 하며 공식
`eightmm/codex-science` repository를 가리켜야 합니다. Updater가 사용자에게
표시한 정확한 commit을 staging에 clone하고 fast-forward ancestry와 runtime을
검증한 뒤 관리 checkout을 원자적으로 교체하고 설치 cache를 확인합니다.
실패하면 이전 checkout으로 rollback합니다. 현재 작업의 load된 cache는
물론 기존 version cache도 모두 보존하므로 이미 열린 작업의 고정된 hook path가
유지됩니다. 업데이트 적용본은 new Codex task를 열어 사용합니다.
최근 update 알림이 없다면 첫 요청은 정확한 commit을 확인해 표시만 합니다.
같은 요청을 한 번 더 보내야 표시된 commit 설치를 승인합니다.

고급 mode는 Codex를 실행하기 전에 process environment로 설정합니다:

```bash
CODEX_SCIENCE_AUTO_UPDATE=notify  # 기본값: 확인 후 알림
CODEX_SCIENCE_AUTO_UPDATE=off     # 자동 확인 중지
```

무인 apply mode는 없습니다. Update는 위 평문 요청으로 매번 명시적으로
승인해야 합니다. Dirty checkout, fork, custom remote, 승인 후 branch 이동,
non-fast-forward 변경, 동일 cachebuster, staging self-check 실패, plugin cache
검증 실패에서는 업데이트를 거부합니다. 개발용 checkout을 자동으로
덮어쓰지 않습니다.

사용 예시:

```text
Codex Science 시작
현재 고정된 plugin으로 이 데이터를 분석하고 run provenance를 저장해줘.
Codex Science 업데이트
# 새 Codex 작업을 열고 업데이트된 버전으로 계속 진행
```

## 설치 확인과 문제 해결

Codex가 설치된 버전을 인식하는지 확인합니다:

```bash
codex plugin list
```

`codex-science@codex-science` 행이 `installed, enabled`여야 합니다. Mode가
활성화되지 않으면 **새** Codex 작업을 열고 `/hooks`에서 Codex Science hook 세
개를 모두 신뢰한 뒤 정확히 `Start Codex Science` 또는 `Codex Science 시작`을
입력하세요. 업데이트 후에는 새 작업을 열어야 하며, hook 정의가 바뀌었다면 다시
검토하고 신뢰해야 합니다.

개발 checkout에서는 다음을 실행합니다:

```bash
./scripts/check.sh fast    # offline unit, catalog, plugin, skill 검증
./scripts/doctor.sh        # checkout, submodule, catalog, 환경 진단
./scripts/check.sh public  # 선택적 live public-source smoke test
```

이 저장소에서 `codex plugin marketplace add "$PWD"`를 실행하지 마세요. curl
installer가 `codex-science` marketplace 등록을 소유하며 `~/.codex-science`를
가리키도록 관리합니다.

경로 override와 설치 세부사항은 [설치 문서](docs/SETUP.md), 상태와 복구 계약은
[Checkpoint 문서](docs/CHECKPOINTS.md)를 참고하세요.

## 과학 컴퓨터 활용

활성 작업 안에서 Codex Science는 로컬 shell, Python, R, Julia, Jupyter,
container, CPU, GPU 환경을 탐지하고 실제 과학 계산에 사용할 수 있습니다.
필요하면 사용자가 이미 보유한 SSH host, Slurm/HPC cluster, cloud GPU 계정,
private object storage도 사용합니다. GUI/browser desktop 자동화는 의도적으로
이 워크플로에서 제외합니다.

읽기 전용 점검과 기존 환경의 작은 계산은 바로 진행합니다. Package 설치,
새 host 접속, private data 전송, 원격 job 제출, 유료 자원 할당 전에는 target,
data movement, 자원, 시간·비용 상한, output path, 취소 계획을 하나의 승인
packet으로 제시합니다. 승인된 reversible 단계는 반복 확인 없이 이어서
진행합니다. 명령, 환경, job ID, log, exit status, 비용, output hash는
`artifacts/<run-id>/`에 기록하며 credential은 기록하지 않습니다. 전체 경계는
[과학 컴퓨팅](docs/COMPUTE.md)을 참고하세요.

완료된 각 run에는 로컬 `index.md`가 생성되고, 요청 시 offline `index.html`도
생성됩니다. 주요 PNG/JPEG/WebP/GIF 결과는 Codex 대화에 직접 표시하고,
report·table·notebook·log·보조 figure는 클릭 가능한 절대경로 링크로
제공합니다. 별도 웹 배포는 필요하지 않습니다.

새 작업에서 평범한 과학 질문만으로는 모드가 활성화되지 않습니다. Codex에 등록되는 코어 스킬은 3개뿐이며, 280개 카탈로그 wrapper는 내부 카탈로그에 남아 활성 coordinator가 선택할 때만 로드됩니다.

> 카탈로그에 있다고 실행 권한이 생기는 것은 아닙니다. 비활성 스킬은 audit 사유를 표시하고, upstream 지침을 열람하기 전에 확인을 요구합니다. 검증·설정·경계는 [docs/](docs/) 참고.

## 카탈로그

모든 스킬은 하나의 결정적·감사된 inventory(`catalog/inventory.json`)로 병합되며, 세 티어로 구성됩니다:

- **K-Dense-AI — 149** · pinned upstream(Git 서브모듈); 얇은 Codex wrapper가 고정된 지침을 가리킴.
- **Codex-native 저작 — 128** · Google DeepMind 과학 스킬 전체, 공개 교재 기반 수학·물리 워크플로 28개, 에이전틱 생명과학 source·synthesis workflow 25개, protocol 기반 literature-review conductor, 분광·NMR·MS·XRD/산란·크로마토그래피·통합 구조규명 워크플로 6개, 로컬·원격 과학 컴퓨팅, 최신 구조·단백질/유전체·도킹·설계·MD·single-cell 모델을 [격리·승인형 실행 스킬](authored-skills/)로 제공. 실제 문제가 주어지면 전용 runner가 풀이·독립 검증·provenance·review까지 이어서 수행. 공개 source 34개와 로컬 catalog 검색·life-science planner는 plugin read-only MCP(`science_search_*`, `science_plan_*`)로 직접 호출. [생명과학 source 지원표](docs/LIFE_SCIENCE_RESEARCH_SOURCES.md) 참고.
- **DeepMind 인프라 — 3** · `credentials`, `uv`, `workflow_skill_creator`는 포인터로 유지.

보수적 audit이 각 스킬을 **active/inactive**로 표시합니다(라이선스·실행 코드·인증정보·안전성 기준). 비활성 스킬은 카탈로그에 남되 사용 전 명시적 확인을 요구합니다.

`doctor.sh`는 모든 Codex-native 원본과 생성 wrapper를 검증하고, 고정된 source의 무결성과 자연어 스킬 이름 검색을 확인합니다. 500줄을 넘는 upstream 지침의 wrapper는 전체 source tree를 기본 로드하지 않고 heading-first progressive loading을 사용합니다.

## 라이선스

Codex Science의 원본 코드는 [MIT License](LICENSE)로 배포됩니다.

가져오거나 각색한 스킬은 각자의 upstream 라이선스를 유지합니다:

- **K-Dense-AI/scientific-agent-skills** — 고정된 Git 서브모듈; 라이선스는 각 `SKILL.md`에 개별 명시.
- **Google DeepMind/science-skills** — Apache-2.0 + CC-BY-4.0. 과학 스킬은 `authored-skills/`에서 Codex-native로 각색(각 `SKILL.md`에 attribution 명시); `vendor/gdm-science-skills/`의 pinned 원본 복사본은 `LICENSE`·`SKILL_LICENSES.md`·`PROVENANCE.md`를 그대로 보존.
- **공개 수학·물리 교재** — 출처 URL, 내려받은 파일의 정확한 해시, 라이선스, 제외 기준과 PDF 비커밋 정책을 [`docs/TEXTBOOK_SOURCES.md`](docs/TEXTBOOK_SOURCES.md)에 기록. 스킬은 교재 복사본이 아니라 독립적으로 작성한 문제 해결 절차임.
- **분석화학 표준·도구** — 공식 출처, 기존 도구와의 역할 경계, modality별 증거 규칙을 [`docs/ANALYTICAL_SOURCES.md`](docs/ANALYTICAL_SOURCES.md)에 기록.

저장소 수준 파일은 개별 스킬이나 의존성의 라이선스를 덮어쓰지 않습니다.
