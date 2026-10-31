# CLAUDE.md - <infra-repo> (Terraform / cloud infrastructure)

## Commands
```bash
terraform fmt -check -recursive
terraform validate
terraform plan -out=tfplan        # plan only; applying is a human step
```

## Rules
- Claude may run `fmt`, `validate`, and `plan`. Claude must never run `apply` or `destroy`.
- Every resource is tagged: owner, environment, cost-centre.
- Modules are versioned; pin versions, no `latest`.
- State is remote and locked; never edit state files by hand.
- Least privilege: new IAM policies list explicit actions and resources, no `*:*`.

## Review checklist for plans
1. Any resource being destroyed or replaced? Explain why.
2. Any public ingress (0.0.0.0/0)? Needs written justification.
3. Cost impact estimate for new compute/storage.
4. Rollback path.
