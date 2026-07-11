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

Codex Science는 하나의 Codex 작업을 옵트인 방식의 과학 워크벤치로 바꿉니다: 한 번 시작하면 이후 턴에서 연구 워크플로가 이어지고, 명시적으로 종료합니다. [K-Dense-AI](https://github.com/K-Dense-AI/scientific-agent-skills)에서 pin한 149개에, [Google DeepMind](https://github.com/google-deepmind/science-skills) 과학 스킬 전체, 공개 교재 기반 수학·물리 워크플로 28개, 실험 분광·분석화학, 로컬·원격 과학 컴퓨팅, Claude Science 공개 featured workflow, ESMFold2·ESMC·AlphaFold3·Protenix-v2·SimpleFold·RoseTTAFold All-Atom·RFdiffusion·BindCraft 같은 최신 공개 모델의 [Codex-native 저작본](authored-skills/)을 더한 **254개 감사된 에이전트 스킬** 카탈로그로 작업을 라우팅합니다.

Claude Science의 공개 워크플로에서 영감을 받은 독립 Codex 플러그인이며, 비공개 구현과의 동등성을 주장하지 않습니다.

## 설치

**한 번만** 설치하면 Codex에 전역 등록되어 이후 모든 프로젝트에서 쓸 수 있습니다:

```bash
curl -fsSL https://raw.githubusercontent.com/eightmm/codex-science/main/scripts/install.sh | bash
```

Codex CLI, Git, Python 3.11+ 가 필요합니다(런타임은 순수 Python 표준 라이브러리 — 패키지·가상환경·`uv` 없이 실행). 설치 스크립트는 `~/.codex-science`에 clone하고 플러그인을 전역 등록한 뒤 런타임 self-check까지 수행하며, 업데이트하려면 다시 실행하면 됩니다.

그다음 **아무** 프로젝트에서나 새 Codex 작업을 시작하고 `/hooks`를 열어 Codex Science의 `SessionStart`·`UserPromptSubmit` hook을 한 번 신뢰 처리하세요. `Start Codex Science`(또는 `Codex Science 시작`)라고 하면 이후 턴에서는 coordinator가 스스로 재호출됩니다. 프로젝트마다 재설치하지 않습니다.

`/hooks`는 사람이 확인하는 보안 경계입니다. Plugin command를 승인할 뿐
science mode를 시작하지는 않으므로, 이 승인은 사용자가 직접 처리하는 것이
맞습니다. 신뢰 처리 뒤에는 평문 시작 문구로 mode가 활성화됩니다. Codex에게
hook script를 직접 실행하라고 요청할 필요가 없으며, 직접 실행은 hook 신뢰를
대체하지도 않습니다.

<details>
<summary>수동 / 개발용 설치</summary>

```bash
git clone https://github.com/eightmm/codex-science.git
cd codex-science
./scripts/bootstrap.sh
codex plugin marketplace add "$PWD"
codex plugin add codex-science@codex-science
```

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

활성 상태는 Codex의 `session_id`에 연결됩니다. Hook은 plugin writable data directory에 해시된 marker만 저장하며 prompt나 연구 데이터는 저장하지 않습니다. 이후 매 턴과 resume/context compaction 뒤에 coordinator context를 다시 주입합니다. `clear`, 새 작업, 명시적 종료에서는 marker를 제거하거나 무시하며, 방치된 marker는 180일 동안 사용되지 않으면 만료됩니다. Hook을 아직 신뢰하지 않았다면 같은 작업의 대화 문맥을 통한 best-effort 지속만 가능하며 resume/compaction 보존은 보장되지 않습니다.

명시적으로 종료합니다:

```text
Stop Codex Science
Codex Science 종료
```

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

새 작업에서 평범한 과학 질문만으로는 모드가 활성화되지 않습니다. Codex에 등록되는 코어 스킬은 3개뿐이며, 254개 카탈로그 wrapper는 내부 카탈로그에 남아 활성 coordinator가 선택할 때만 로드됩니다.

> 카탈로그에 있다고 실행 권한이 생기는 것은 아닙니다. 비활성 스킬은 audit 사유를 표시하고, upstream 지침을 열람하기 전에 확인을 요구합니다. 검증·설정·경계는 [docs/](docs/) 참고.

## 카탈로그

모든 스킬은 하나의 결정적·감사된 inventory(`catalog/inventory.json`)로 병합되며, 세 티어로 구성됩니다:

- **K-Dense-AI — 149** · pinned upstream(Git 서브모듈); 얇은 Codex wrapper가 고정된 지침을 가리킴.
- **Codex-native 저작 — 102** · Google DeepMind 과학 스킬 전체, 공개 교재 기반 수학·물리 워크플로 28개, 분광·NMR·MS·XRD/산란·크로마토그래피·통합 구조규명 워크플로 6개, 로컬·원격 과학 컴퓨팅, 최신 구조·단백질/유전체·도킹·설계·MD·single-cell 모델을 [격리·승인형 실행 스킬](authored-skills/)로 제공. 실제 문제가 주어지면 전용 runner가 풀이·독립 검증·provenance·review까지 이어서 수행. 공개 소스 15개는 plugin read-only MCP(`science_search_*`)로 직접 호출.
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
