# git 이력에서 폴더를 빼면 작업 트리의 그 폴더 파일까지 지워진다 — filter-branch 함정 (범용)

## 함정

원격 첫 푸시 전에 "설계도·인수인계 같은 로컬 전용 폴더를 과거 커밋에서도 빼자"며
`git filter-branch --index-filter 'git rm -r --cached --ignore-unmatch -- 폴더'`를 돌리면,
`--cached`라서 로컬 파일은 안전할 것 같지만 **아니다**. 재작성이 끝나면 git이 새 HEAD를 체크아웃하는데,
옛 HEAD에서 추적되던 파일이 새 HEAD에 없으니 **작업 트리에서 삭제한다.** `git filter-repo`도 같다.
미추적 파일(원래 .gitignore 대상)은 안 건드려서 "일부만 남은" 폴더가 돼 더 늦게 눈치챈다.

## 원칙 — 백업 → 재작성 → 즉시 복원 → 대조 → ignore

1. 재작성 전 백업: `git bundle create <저장소 밖 경로>.bundle --all` + `git bundle verify`.
2. 재작성(filter-branch는 `refs/original/`에 옛 브랜치를 남긴다 — 복원 원천).
3. **바로 복원**: `git archive refs/original/refs/heads/main -- 폴더1 폴더2 | tar -x`
   (checkout으로 꺼내면 다시 인덱스에 올라감 — archive는 작업 트리에만 풀린다).
4. 대조: 각 파일 `git show <옛ref>:<경로>`와 비교. autocrlf=true면 줄바꿈(CRLF)만 다르게 나오는 게 정상 —
   `tr -d '\r'` 후 비교해 내용 일치 확인.
5. `.gitignore`에 폴더 추가 → 커밋 → `git log main --name-only | grep '^폴더/'`가 0인지 확인 후 푸시
   (푸시는 `main`만 — `--all`/`--mirror`면 `refs/original`의 옛 이력이 같이 올라간다).
6. 커밋 해시가 거의 다 바뀐다 — 문서에 적어 둔 해시는 "옛 해시 → 새 해시" 대응표를 남긴다(문서 전용
   커밋은 `--prune-empty`로 사라지므로 그 시점의 코드 상태 커밋으로 대응).

## 이미 푸시한 뒤라면

재작성 + force-push는 협업자 사본·포크·캐시에 옛 이력이 남아 완전 제거가 안 된다 — 시크릿이면 재작성보다
**폐기(재발급)**가 먼저. 이 함정은 "첫 푸시 전"이 유일하게 깔끔한 시점이라는 것까지 포함한다.

## 실측 사례

Market_Agent_App(2026-10-06, D-033): GitHub 사설 저장소 첫 푸시 전 `설계도/`·`인수인계/`를 이력에서 제거
(38 → 24커밋). 재작성 직후 두 폴더의 추적 파일 10개가 작업 트리에서 사라짐 → refs/original에서 archive로
복원, 10개 전부 내용 일치(줄바꿈만 CRLF) 확인 후 진행. 미추적이던 실행규격서·시연영상은 영향 없음.

## 같은 함정 — 추적 해제(git rm --cached) 뒤 브랜치 이동·병합 (JudgeCal, 2026-10-12)
- 추적 중이던 DB 파일을 `git rm --cached` + `.gitignore`로 빼고 **그 브랜치에서만** 커밋해 두면, 아직 추적 중인 main으로 `git checkout main`할 때 무시(ignore)된 로컬 파일이 main의 커밋본으로 **조용히 덮어써지고**, 이어서 `git merge --ff-only`가 그 파일을 삭제한다. 경고가 안 나온다(ignore 파일은 덮어쓰기 대상). 사용자가 로컬에서 수정해 둔 사본이 있었다면 그 변경이 사라진다.
- 원칙: 추적 해제 커밋을 main에 합치기 **전에** 해당 파일을 브랜치 밖으로 복사 백업(`cp data/x.db <scratch>/`)하고, 합친 뒤 원래 자리에 되돌려 대조한다. 합친 직후 `ls`로 파일이 있는지 확인한다.
- 부수 확인: "잔여물(-shm/-wal)만 삭제"하는 작업 전에는 본체 파일 존재와 크기를 먼저 확인하고, 삭제 뒤에도 본체를 다시 확인한다.

