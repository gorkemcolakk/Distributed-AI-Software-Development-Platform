# Definition of Done (DoD)

**Status: Active.** The Scrum Team agrees on this standard and reviews it for potential improvements during Sprint Retrospectives or Sprint Planning. Work that does not meet this Definition of Done is not part of the Increment and cannot be considered complete.

A Product Backlog Item (Trello Card) is **Done** when all of the following criteria are met:

1. **Acceptance Criteria:** All acceptance criteria specified in the item are fully met and verified.
2. **Code is on `main`:** The code is integrated through a GitHub Pull Request (PR) that:
   - has passing CI (lint + unit tests for `master` and `agent`);
   - was reviewed and approved by at least one teammate other than the author;
   - is successfully merged into the `main` branch without conflicts.
3. **Tests:** New logic has appropriate unit tests that run successfully without a real model. Behaviour involving a model was also tested with the real local model, and the execution result is explicitly noted in the pull request.
4. **Runs in the real setup:** The system starts successfully using the project's local execution script (`start.bat`) without syntax or runtime errors. The new feature works as expected in the browser on both desktop and mobile widths.
5. **Privacy and security:** There are no secrets or hardcoded credentials in the repository, no data is sent to external AI services, and all model outputs are treated as untrusted.
6. **Documentation:** 
   - README, SRS, architecture, or member guides are updated when the item changes them.
   - Any new API endpoints or architectural changes are documented in the repository.
   - Code variables and comments are in English.
   - User-facing text (UI) is in Turkish.
7. **Task Board Updated:** The Trello card is moved to the "Done" list, and the relevant GitHub PR link is attached to the card.



# ✅ Definition of Done (DoD)

**Status:** Active 🟢  
*The Scrum Team agrees on this standard and reviews it for potential improvements during Sprint Retrospectives or Sprint Planning. Work that does not meet this Definition of Done is not part of the Increment and cannot be considered complete.*

A Product Backlog Item (Trello Card) is **Done** when all of the following criteria are verified:

| Category | 📌 Criteria | Check |
| :--- | :--- | :---: |
| 🎯 **Acceptance** | All acceptance criteria specified in the Trello card are fully met and verified. | `[ ]` |
| 💻 **Code & PR** | The code is integrated through a GitHub Pull Request (PR) to `main`. | `[ ]` |
| 💻 **Code & PR** | PR was reviewed and approved by at least one teammate other than the author. | `[ ]` |
| 💻 **Code & PR** | PR is successfully merged into the `main` branch without conflicts. | `[ ]` |
| 🧪 **Testing & CI** | CI pipeline is passing (lint + unit tests for `master` and `agent`). | `[ ]` |
| 🧪 **Testing & CI** | New logic has unit tests that run successfully without a real model. | `[ ]` |
| 🧪 **Testing & CI** | Model-dependent behavior is tested locally; execution results are noted in the PR. | `[ ]` |
| 🚀 **Execution** | System starts successfully using `start.bat` without syntax/runtime errors. | `[ ]` |
| 🚀 **Execution** | The new feature works as expected in the browser (desktop & mobile widths). | `[ ]` |
| 🔒 **Security** | No secrets or hardcoded credentials exist in the repository. | `[ ]` |
| 🔒 **Security** | No data is sent to external AI services; all model outputs are treated as untrusted. | `[ ]` |
| 📚 **Documentation**| README, SRS, architecture, or member guides are updated if affected. | `[ ]` |
| 📚 **Documentation**| Any new API endpoints or architectural changes are documented in the repo. | `[ ]` |
| 📚 **Documentation**| Code variables and comments are in English; inline comments added for complex logic. | `[ ]` |
| 📚 **Documentation**| User-facing text (UI) is written in Turkish. | `[ ]` |
| 📋 **Task Board** | Trello card is moved to the **"Bitti"** list with the relevant GitHub PR link attached. | `[ ]` |