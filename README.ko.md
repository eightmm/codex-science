# Codex Science

[English](README.md)

Codex Science는 하나의 Codex 작업을 선택적으로 과학 연구 워크벤치로 전환하는 플러그인입니다. 한 번 시작하면 같은 작업의 다음 대화에서도 연구 모드가 유지되고, 명시적으로 종료할 수 있습니다. 다른 Codex 작업에는 영향을 주지 않습니다.

이 프로젝트는 공개된 Claude Science 워크플로를 참고한 독립적인 Codex 플러그인입니다. Anthropic의 비공개 구현을 포함하거나 동일한 제품 수준을 주장하지 않습니다.

## 동작 방식

```text
새 Codex 작업 (비활성)
  -> "Codex Science 시작"
  -> 작업 단위 코디네이터 유지
  -> 감사된 카탈로그 검색
  -> 필요한 내부 스킬 wrapper 선택
  -> 고정된 upstream 지침 적용
  -> provenance 기록 및 근거 검토
  -> "Codex Science 종료"
```

Codex에는 코어 스킬 3개만 등록됩니다. 과학 스킬 wrapper 149개는 내부 카탈로그에 보관되며, 활성화된 코디네이터가 선택할 때만 읽습니다. 따라서 모든 Codex 작업에 전체 카탈로그가 노출되지 않습니다.

## 주요 기능

- 작업 단위 활성화: 한 번 시작하고 같은 작업에서 계속 사용한 뒤 명시적으로 종료합니다.
- 공개 [Scientific Agent Skills](https://github.com/K-Dense-AI/scientific-agent-skills) 149개를 커밋 `4d97e293dc6f604fb6b63dcd49b9028df413d65b`에 고정했습니다.
- 결정론적 감사 인벤토리: 현재 보수적 정책 기준 활성 41개, 비활성 108개입니다.
- 고정된 upstream 카탈로그를 수정하지 않고 Codex 호환 wrapper를 생성합니다.
- PubMed, arXiv, UniProt 읽기 전용 MCP 검색 도구를 제공합니다.
- 실행 명령, 환경, 해시, 주장, 근거, 검토 결과를 재현 가능한 artifact manifest로 기록합니다.
- 인증정보, 패키지 설치, 원격 계산, 외부 쓰기, 유료 서비스, 가져온 실행 코드에는 별도 확인 절차를 적용합니다.

카탈로그에 존재한다고 실행 권한이 부여되는 것은 아닙니다. 비활성 스킬은 감사 사유를 먼저 보여주며, upstream 지침을 확인하려면 사용자의 명시적 동의가 필요합니다.

## 요구사항

- 플러그인을 지원하는 Codex 앱 또는 Codex CLI
- Git 및 서브모듈 지원
- Python 3.11 이상
- [`uv`](https://docs.astral.sh/uv/)

## 저장소에서 설치

```bash
git clone --recurse-submodules https://github.com/eightmm/codex-science.git
cd codex-science
./scripts/bootstrap.sh
codex plugin marketplace add "$PWD"
codex plugin add codex-science@codex-science
```

설치 후에는 플러그인과 MCP 서버가 로드되도록 새 Codex 작업을 시작합니다.

## 사용법

새 작업에서 한 번 시작합니다.

```text
Codex Science 시작
```

영문 시작 문구도 지원합니다.

```text
Start Codex Science
Activate Codex Science
```

이후 같은 작업에서는 스킬 이름을 반복하지 않고 연구를 계속하면 됩니다.

```text
이 가설과 관련된 최신 1차 문헌을 찾아줘.
가설을 반증할 수 있는 가장 작은 실험을 설계해줘.
이 결과를 분석하고 재현 가능한 artifact로 남겨줘.
실행 기록을 기준으로 최종 주장을 검토해줘.
```

명시적으로 종료합니다.

```text
Codex Science 종료
Stop Codex Science
```

새 작업에서 일반적인 과학 질문만 하는 경우에는 Codex Science가 자동 활성화되지 않습니다.

## 검증

결정론적 검사를 실행합니다.

```bash
./scripts/check.sh fast
./scripts/check.sh doctor
```

공개 데이터 소스에 대한 읽기 전용 smoke test를 실행합니다.

```bash
./scripts/check.sh public
```

테스트는 149개 wrapper, 등록된 코어 스킬 3개, 카탈로그 재현성, 활성화 정책, MCP 라우팅, artifact, 검토 입력을 확인합니다.

## 저장소 구조

```text
.codex-plugin/                 플러그인 manifest
skills/                        등록된 작업 단위 코어 스킬 3개
catalog/codex-skills/          내부 Codex wrapper 149개
catalog/inventory.json         결정론적 활성화 인벤토리
vendor/scientific-agent-skills 고정된 upstream Git 서브모듈
src/codex_science/             카탈로그, MCP, artifact, review 구현
scripts/                       설정, 생성, 감사, 검사 도구
tests/                         단위 및 통합 테스트
```

## 현재 경계

- 과학 패키지는 선택된 작업에 필요하고 사용자가 승인한 경우에만 설치합니다.
- Claude Science의 네이티브 artifact UI, 관리형 영구 Python/R kernel, 비공개 connector는 제공하지 않습니다.
- reviewer 결과는 명백한 불일치를 줄이지만 과학적·임상적·규제적 타당성을 보장하지 않습니다.
- 긴 작업의 지속성은 Codex 대화 컨텍스트에 의존하므로, 컨텍스트 압축은 현재 경계로 취급합니다.

## Upstream 및 저작권

가져온 스킬 콘텐츠는 고정된 Git 서브모듈에 보존되며 upstream의 저작자 표시와 라이선스를 유지합니다. 이 저장소의 파일은 개별 스킬이나 의존성의 라이선스를 덮어쓰지 않습니다.
