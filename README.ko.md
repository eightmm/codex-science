<p align="center">
  <img src="assets/codex-science-banner.svg" alt="Codex Science" width="100%">
</p>

<p align="center">
  <a href="README.md">English</a> ·
  <a href="docs/SETUP.md">설치</a> ·
  <a href="docs/">문서</a>
</p>

Codex Science는 하나의 Codex 작업을 옵트인 방식의 과학 워크벤치로 바꿉니다: 한 번 시작하면 이후 턴에서 연구 워크플로가 이어지고, 명시적으로 종료합니다. 두 upstream 소스([K-Dense-AI](https://github.com/K-Dense-AI/scientific-agent-skills), [Google DeepMind](https://github.com/google-deepmind/science-skills))에서 온 **187개 감사된 에이전트 스킬** 카탈로그로 작업을 라우팅하고, 읽기 전용 공개 데이터 도구를 더하며, 재현 가능한 artifact와 독립 근거 검토를 기록합니다.

Claude Science의 공개 워크플로에서 영감을 받은 독립 Codex 플러그인이며, 비공개 구현과의 동등성을 주장하지 않습니다.

## 설치

플러그인을 지원하는 Codex 앱/CLI, Git, Python 3.11+ 가 필요합니다. 런타임은 순수 Python 표준 라이브러리라 설치할 패키지가 없습니다.

```bash
git clone https://github.com/eightmm/codex-science.git
cd codex-science
./scripts/bootstrap.sh
codex plugin marketplace add "$PWD"
codex plugin add codex-science@codex-science
```

`bootstrap.sh`가 Python을 확인하고 고정된 upstream 스킬 서브모듈을 얕게 받아옵니다. 설치 후 플러그인과 MCP 서버가 로드되도록 **새** Codex 작업을 시작하세요.

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

## 라이선스

Codex Science의 원본 코드는 [MIT License](LICENSE)로 배포됩니다.

가져온 스킬은 각자의 upstream 라이선스를 유지합니다:

- **K-Dense-AI/scientific-agent-skills** — 고정된 Git 서브모듈; 라이선스는 각 `SKILL.md`에 개별 명시.
- **Google DeepMind/science-skills** — `vendor/gdm-science-skills/`에 vendoring; Apache-2.0(코드) + CC-BY-4.0, 데이터 출처 약관은 `SKILL_LICENSES.md`, 출처는 `PROVENANCE.md`.

저장소 수준 파일은 개별 스킬이나 의존성의 라이선스를 덮어쓰지 않습니다.
