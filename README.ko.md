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

Codex Science는 하나의 Codex 작업을 옵트인 방식의 과학 워크벤치로 바꿉니다: 한 번 시작하면 이후 턴에서 연구 워크플로가 이어지고, 명시적으로 종료합니다. [K-Dense-AI](https://github.com/K-Dense-AI/scientific-agent-skills)에서 pin한 149개에, [Google DeepMind](https://github.com/google-deepmind/science-skills) 과학 스킬 전체의 [Codex-native 저작본](authored-skills/)을 더한 **187개 감사된 에이전트 스킬** 카탈로그로 작업을 라우팅하고, 읽기 전용 공개 데이터 도구를 더하며, 재현 가능한 artifact와 독립 근거 검토를 기록합니다.

Claude Science의 공개 워크플로에서 영감을 받은 독립 Codex 플러그인이며, 비공개 구현과의 동등성을 주장하지 않습니다.

## 설치

**한 번만** 설치하면 Codex에 전역 등록되어 이후 모든 프로젝트에서 쓸 수 있습니다:

```bash
curl -fsSL https://raw.githubusercontent.com/eightmm/codex-science/main/scripts/install.sh | bash
```

Codex CLI, Git, Python 3.11+ 가 필요합니다(런타임은 순수 Python 표준 라이브러리). 설치 스크립트는 `~/.codex-science`에 clone하고 플러그인을 전역 등록하며, 업데이트하려면 다시 실행하면 됩니다.

그다음 **아무** 프로젝트에서나 새 Codex 작업을 시작하고 `Start Codex Science`(또는 `Codex Science 시작`)라고 하세요. 프로젝트마다 재설치하지 않습니다.

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

명시적으로 종료합니다:

```text
Stop Codex Science
Codex Science 종료
```

새 작업에서 평범한 과학 질문만으로는 모드가 활성화되지 않습니다. Codex에 등록되는 코어 스킬은 3개뿐이며, 187개 카탈로그 wrapper는 내부 카탈로그에 남아 활성 coordinator가 선택할 때만 로드됩니다.

> 카탈로그에 있다고 실행 권한이 생기는 것은 아닙니다. 비활성 스킬은 audit 사유를 표시하고, upstream 지침을 열람하기 전에 확인을 요구합니다. 검증·설정·경계는 [docs/](docs/) 참고.

## 카탈로그

모든 스킬은 하나의 결정적·감사된 inventory(`catalog/inventory.json`)로 병합되며, 세 티어로 구성됩니다:

- **K-Dense-AI — 149** · pinned upstream(Git 서브모듈); 얇은 Codex wrapper가 고정된 지침을 가리킴.
- **Codex-native 저작 — 35** · Google DeepMind 과학 스킬 전체를 [1급 Codex 스킬로 재작성](authored-skills/) — Codex 도구와 플러그인 read-only MCP(`science_search_*`) 또는 공개 REST/GraphQL API에 매핑.
- **DeepMind 인프라 — 3** · `credentials`, `uv`, `workflow_skill_creator`는 포인터로 유지.

보수적 audit이 각 스킬을 **active/inactive**로 표시합니다(라이선스·실행 코드·인증정보·안전성 기준). 비활성 스킬은 카탈로그에 남되 사용 전 명시적 확인을 요구합니다.

## 라이선스

Codex Science의 원본 코드는 [MIT License](LICENSE)로 배포됩니다.

가져오거나 각색한 스킬은 각자의 upstream 라이선스를 유지합니다:

- **K-Dense-AI/scientific-agent-skills** — 고정된 Git 서브모듈; 라이선스는 각 `SKILL.md`에 개별 명시.
- **Google DeepMind/science-skills** — Apache-2.0 + CC-BY-4.0. 과학 스킬은 `authored-skills/`에서 Codex-native로 각색(각 `SKILL.md`에 attribution 명시); `vendor/gdm-science-skills/`의 pinned 원본 복사본은 `LICENSE`·`SKILL_LICENSES.md`·`PROVENANCE.md`를 그대로 보존.

저장소 수준 파일은 개별 스킬이나 의존성의 라이선스를 덮어쓰지 않습니다.
