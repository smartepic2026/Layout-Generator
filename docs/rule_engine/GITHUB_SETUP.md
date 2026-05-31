# GitHub 업로드 가이드 (내 컴퓨터에서 직접)

> 코드 준비는 끝났습니다(requirements.txt · README.md · .gitignore · verify_pipeline.py).
> 아래 명령을 **내 Windows 컴퓨터의 PowerShell**에서 실행하면 GitHub에 올라갑니다.
> (자동화 도구로는 올릴 수 없어 — github.com 접근·git 동작이 차단된 환경 — 이 마지막 단계만 직접 해주세요.)

---

## 0. ⚠️ 먼저 정리: 깨진 .git 폴더 삭제

자동화 중 생성하다 만 `.git` 폴더가 남아 있습니다. 먼저 지워주세요.

PowerShell에서 프로젝트 폴더로 이동 후:
```powershell
cd "C:\Users\User\OneDrive - SKKU\claude_cowork_file"
Remove-Item -Recurse -Force .git
```
(폴더 탐색기에서 숨김 파일 보기 → `.git` 폴더 삭제해도 됩니다.)

---

## 1. GitHub에서 빈 저장소 만들기

1. https://github.com 로그인 → 우상단 **+** → **New repository**.
2. 저장소 이름 입력(예: `biopharm-layout-system`).
3. **⚠️ Private(비공개) 선택** — RAG DB에 저작권 문서 본문이 있어 공개 금지.
4. README/.gitignore 추가 옵션은 **체크하지 말고**(이미 있음) **Create repository**.
5. 다음 화면의 저장소 주소(`https://github.com/<계정>/biopharm-layout-system.git`) 복사.

---

## 2. 내 컴퓨터에서 올리기 (PowerShell)

프로젝트 폴더 안에서 순서대로:
```powershell
cd "C:\Users\User\OneDrive - SKKU\claude_cowork_file"

git init
git add -A
git commit -m "Initial commit: Rule Engine + rag_interface + RAG validator"

git branch -M main
git remote add origin https://github.com/<계정>/biopharm-layout-system.git
git push -u origin main
```
- `<계정>` 부분을 실제 GitHub 계정명으로 바꾸세요.
- push 할 때 GitHub 로그인(브라우저 인증 또는 토큰)이 한 번 뜹니다.

---

## 3. 잘 올라갔는지 확인

- GitHub 저장소 페이지 새로고침 → `rule_engine/`, `rag_interface/`, `RAG_DB_build/`,
  `README.md`, `verify_pipeline.py` 가 보이면 성공.
- 자동 제외된 것(정상): `RAG_DB_files/`(저작권 원본), `target/`(무관 프로젝트),
  `__pycache__/`, `validation_runs_demo/`, 백업 xlsx. → `.gitignore`가 처리.

---

## 4. 팀원이 받아서 실행

팀원은 [설치 How-to(Notion)] 대로:
```powershell
git clone https://github.com/<계정>/biopharm-layout-system.git
cd biopharm-layout-system
pip install -r requirements.txt
python verify_pipeline.py
```

---

## 참고 — 무엇이 올라가나 (예상)

| 포함 | 제외(.gitignore) |
| --- | --- |
| rule_engine/ (코드·테스트·golden·output_example.json) | RAG_DB_files/ (저작권 원본 PDF 27M) |
| rag_interface/ (search·backend·profiles) | target/ (무관 프로젝트) |
| RAG_DB_build/ (vector_store + data/ 빌드된 DB 36M) | __pycache__/, *.pyc |
| URS xlsx, requirements.txt, README, verify_pipeline.py, CLAUDE.md | validation_runs_demo/, *.backup_*.xlsx |

> 용량: 약 38MB (data/ 임베딩 포함). GitHub 파일당 100MB 제한 이내.

---

> 작성일: 2026-05-29
