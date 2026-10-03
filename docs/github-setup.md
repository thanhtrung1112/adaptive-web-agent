# Thiết lập GitHub (GitHub CLI `gh`)

Thay `OWNER` bằng tài khoản/organization của nhóm.

```bash
# 1. Tạo repo riêng và đẩy mã nguồn
git init && git add . && git commit -m "#1 chore: init repo W1 deliverables"
gh repo create OWNER/adaptive-web-agent --private --source=. --remote=origin --push

# 2. Milestones
gh api repos/OWNER/adaptive-web-agent/milestones -f title="W1-W4: Benchmark + semantic locator" -f due_on="2026-10-24T23:59:59Z"
gh api repos/OWNER/adaptive-web-agent/milestones -f title="W5-W8: Agent + self-healing + harness" -f due_on="2026-11-21T23:59:59Z"
gh api repos/OWNER/adaptive-web-agent/milestones -f title="W9-W11: Ablation + final test" -f due_on="2026-12-12T23:59:59Z"
gh api repos/OWNER/adaptive-web-agent/milestones -f title="W12-W14: Report + release" -f due_on="2026-12-31T23:59:59Z"

# 3. Branch protection cho main (yêu cầu 1 review)
gh api -X PUT repos/OWNER/adaptive-web-agent/branches/main/protection --input - <<'JSON'
{
  "required_status_checks": null,
  "enforce_admins": false,
  "required_pull_request_reviews": {"required_approving_review_count": 1},
  "restrictions": null
}
JSON
```

## Issues W1 (gắn milestone "W1-W4")
| # | Tiêu đề |
|---|---|
| 1 | Khởi tạo repo, quy ước commit, branch protection |
| 2 | Viết benchmark spec v0.1 (`docs/benchmark-spec.md`) |
| 3 | Định nghĩa task schema + validator |
| 4 | Viết 10 pilot tasks (`tasks/pilot_tasks.json`) |
| 5 | ADR-0001: stack MiniBiz và cơ chế mutation |
| 6 | Weekly Evidence Package W1 |

```bash
gh issue create -t "Viết benchmark spec v0.1" -b "W1 deliverable" -m "W1-W4: Benchmark + semantic locator"
```

Chia việc theo yêu cầu đề cương: mỗi thành viên vừa viết spec/task vừa code, không tách "một người code, một người viết báo cáo".
