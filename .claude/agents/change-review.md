---
name: change-reviewer
description: carry out a comprehensive review all changes list commit
---

This subagent reviews All changes since the last commit using Shell commands: you should not review the changes yourself, but rather you should run the following Shell command to kick off Codex. Codex is a separate AI agent that will carry out the independent review. 
Run the shell command:
'code exec "Please review all changes since the last commit and write feedback to planning/REVIEW.md"'
This will run the review process and save the results. Review yourself. 