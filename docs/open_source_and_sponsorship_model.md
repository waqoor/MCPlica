# MCPlica Open Source and Sponsorship Model

**Status:** Authoritative governance, licensing, contribution, ownership, and sustainability specification  
**Date:** 2026-08-24

## 1. Document ownership

This document owns the project's **open-source governance and sustainability model**: license policy, Contributor License Agreement (CLA), contribution rules, GitHub organization governance, maintainer authority, intellectual-property ownership, generated-output policy, sponsorship, grants, sponsor recognition, development sponsorship, consulting, future support/SLA relationships, funding milestones, and long-term commercial boundaries.

It does not define application billing because **the application has no sponsorship/subscription entitlement system**. Technical architecture remains authoritative in `architecture.md` and `design_document.md`.

---

## 2. Governing principles

The project shall follow these principles unless this document is explicitly revised by the founder:

1. **The software remains fully open source.** Every product feature is available to everyone under the project license.
2. **Funding may increase development capacity, but never software availability.** No sponsor-only or paid-only features.
3. **Sponsors fund the project/creator; they do not govern the project.** Money does not grant maintainer status, roadmap votes, architectural authority, security privileges, ownership, or exclusivity.
4. **Professional services sell time, expertise, commitments, and support—not privileged software.**
5. **Development sponsorship can accelerate accepted work, but a sponsor cannot force a feature into the roadmap.**
6. **The founder retains final governance authority.** The project is founder-led, not sponsor-led and not automatically democratic.
7. **External code contributions require a CLA. DCO is not used.**
8. **No proprietary commercial-license exception is offered.** There is one public open-source codebase/license model.
9. **Commercial use is permitted only under the open-source license's terms.** The project does not claim that open source can prohibit all commercial use.
10. **User inputs and project-specific generated output remain distinct from the platform/runtime license.**
11. **Sponsor recognition is opt-in.** Funding amounts are private by default.
12. **Funding identity is creator-first across multiple open-source projects**, while specific projects may also receive dedicated sponsorship/development funding.

---

## 3. Project license

### 3.1 License choice

The platform and generic MCP runtime shall be licensed:

```text
GNU Affero General Public License v3.0 only
SPDX-License-Identifier: AGPL-3.0-only
```

The repository root shall contain the unmodified canonical AGPL-3.0 license text in `LICENSE`.

Source files should include SPDX identifiers where practical.

### 3.2 Why AGPL

This is server/network software. The project explicitly does not want a company to take the covered platform, modify it, operate the modified covered version as a network service, and keep those covered modifications proprietary in circumstances where AGPL requires source availability.

AGPL preserves open-source commercial use while imposing strong reciprocal source obligations for covered network-served modifications.

### 3.3 What AGPL does not mean

Project documentation must never falsely claim:

- a commercial user must pay the founder;
- a commercial user must send an upstream pull request;
- all software interacting with the platform automatically becomes AGPL;
- user data/OpenAPI specifications automatically become AGPL;
- every independent service connected over a protocol is automatically owned/licensed by this project.

Compliance depends on the license and the relationship of the software; legal questions should be handled with qualified counsel.

### 3.4 AGPL-only policy

Use `AGPL-3.0-only`, not `AGPL-3.0-or-later`, as the project license identifier unless the founder explicitly changes the policy.

### 3.5 No proprietary/commercial license exception

The project shall not offer:

```text
Community AGPL edition + proprietary commercial edition
```

or a private license allowing a company to keep covered platform modifications proprietary in exchange for money.

This decision is intentional.

### 3.6 No open-core split

No core/enterprise feature separation. There is one feature set.

Forbidden product licensing patterns:

- closed-source enterprise modules required for capabilities listed in the PRD;
- source-available but non-open replacement license for the public codebase;
- license keys controlling functionality;
- paid extensions that are necessary to unlock otherwise implemented core product features.

Independent third-party integrations may exist in the ecosystem under their own compatible licenses, but the official project shall not undermine the “all features available” principle.

---

## 4. Contributor License Agreement model

### 4.1 CLA is mandatory

Every external human contribution that contains copyrightable code/documentation must be covered by the project's CLA before merge.

Use:

- **Individual CLA (ICLA)** for contributors acting in their own capacity;
- **Entity/Corporate CLA (CCLA)** when an employer/entity owns or controls the contributed intellectual property or the contribution is made on the entity's behalf.

### 4.2 DCO is explicitly rejected

The project shall not use DCO as its contribution mechanism.

Do not require:

- `Signed-off-by` commits for legal contribution acceptance;
- Developer Certificate of Origin attestation;
- DCO bot/status check;
- `DCO.md` as a contribution requirement.

A commit may incidentally contain `Signed-off-by`, but it has no project contribution-policy effect.

### 4.3 CLA is a license, not copyright assignment

The project does **not** require contributors to assign copyright ownership to the founder.

Contributors retain ownership of their contributions while granting the rights required for the project to accept, reproduce, modify, combine, distribute, and sublicense the contribution consistently with the project's open-source operation.

The CLA must include appropriate patent-license language and contributor representations that they have the right to submit the contribution.

### 4.4 CLA policy constraints

The final CLA legal text must preserve these policy decisions:

- contributor retains copyright ownership;
- grant is perpetual, worldwide, royalty-free, non-exclusive, and irrevocable to the legally permitted extent;
- project receives rights necessary to incorporate, modify, distribute, and maintain contributions;
- patent rights are granted for contributor-controlled patent claims necessarily infringed by the contribution, using standard CLA principles;
- contributor represents they are entitled to submit the work;
- contributions are provided without a support/warranty obligation except where law/agreement says otherwise;
- signing CLA does not grant contributor governance rights;
- the CLA is not a hidden commitment to a proprietary closed-source edition;
- the project policy remains no proprietary commercial-license exception.

Before public contribution intake is enabled, the founder shall publish a lawyer-reviewed CLA text consistent with these constraints. Legal wording may be refined by counsel; policy substance above may not be weakened without updating this document.

### 4.5 CLA versioning

Each published CLA has a version identifier and effective date.

If material CLA terms change:

- new contributions require acceptance of the new version;
- CLA automation shall request re-signing when appropriate;
- signature records must identify accepted CLA version.

### 4.6 CLA automation

Use the hosted **CLA Assistant GitHub App** or another founder-approved organization-wide CLA system with equivalent behavior.

Required behavior:

- detect PR author/signature coverage;
- comment/instruct unsigned contributors;
- provide authenticated signing flow;
- expose a required PR status check;
- track CLA version/signature records;
- support organization/repository deployment;
- allow entity/corporate process where required.

Do not adopt the archived CLA Assistant Lite GitHub Action as the primary CLA mechanism.

### 4.7 Contribution gate

External PR flow:

```text
Open pull request
      |
      v
CLA status check
  |             |
unsigned       covered
  |             |
  v             v
sign CLA    CI + review
  |             |
  +-------> merge eligibility
```

No external PR containing substantive contribution may be merged while CLA status is failing.

Organization-controlled automation/bot accounts may be explicitly exempted when they do not represent an unlicensed third-party human contribution, but exemptions must be maintained in the CLA system and must never be a manual bypass for ordinary contributors.

---

## 5. Intellectual-property ownership

### 5.1 Founder-owned IP

Copyright in code/documentation authored by the founder remains personally owned by the founder unless explicitly transferred in a future written agreement.

Project trademarks, project name, official logo, official domains, and brand identity are intended to remain personally owned by the founder unless explicitly transferred later.

### 5.2 Contributor-owned contributions

Because the project uses a CLA rather than copyright assignment, contributors retain copyright in their contributions and grant the CLA rights.

Repository notices should use accurate collective wording such as:

```text
Copyright © <Founder> and contributors
```

rather than claiming the founder owns copyright in every community contribution.

### 5.3 Future legal company/entity

The founder may create a company/entity later.

Default relationship:

```text
Founder personally
├── owns founder-authored project copyrights
├── owns project trademarks/brand
└── retains project governance authority

Future company
├── signs consulting contracts
├── signs support/SLA contracts
├── receives/handles commercial payments
├── may administer approved sponsorship agreements
└── does not automatically own project IP
```

The company obtains only permissions/brand use needed through explicit founder authorization/license; there is no automatic IP transfer.

### 5.4 No sponsor ownership

Sponsors, grantors, consulting customers, and development sponsors receive no copyright/trademark ownership merely because they provide money.

A separately commissioned contribution made by a company can be contributed under the CLA and project license; contractual terms must not create exclusive/private ownership of a public project feature.

---

## 6. Generated output and user-content policy

This product processes company-owned materials, so licensing boundaries must be explicit.

### 6.1 User-supplied content

Examples:

- OpenAPI specifications;
- API Inventory files;
- product/API documentation;
- configuration;
- credentials/secrets.

The platform makes **no ownership claim** over these merely because they are uploaded/processed.

The user/company remains responsible for having the rights necessary to process its content through the platform and configured external AI provider.

### 6.2 Project-specific generated outputs

Examples:

- MCP manifest;
- generated mapping/configuration;
- validation/build metadata;
- project-specific deployment configuration;
- generated schemas derived from user inputs.

Policy:

> Project-specific generated output is not automatically forced under an additional restrictive project license merely because the open-source platform generated it.

The company may use its generated project artifacts subject to any rights present in its own inputs and any third-party material actually incorporated.

### 6.3 Generic runtime/platform code remains AGPL

If an export contains or copies the project's generic runtime/platform source code or a derivative covered by AGPL, that covered code remains AGPL.

Recommended export design is therefore:

```text
project manifest/configuration
+
reference to compatible generic runtime image/software
```

rather than copying the entire runtime source into every generated bundle.

### 6.4 `GENERATED_OUTPUTS.md`

The repository shall publish a plain-language generated-output policy matching this section, with a legal disclaimer that users should obtain advice for their own licensing circumstances.

---

## 7. Trademark and brand policy

Create `TRADEMARKS.md`.

Purpose:

- distinguish code-fork rights from official brand identity;
- prevent misleading claims that an unofficial fork/service is the official project;
- define acceptable referential use such as “compatible with” or “fork of”;
- define logo/name use by sponsors and community members;
- prohibit false endorsement.

The policy should permit honest nominative/reference use and must not attempt to use trademark restrictions to negate rights granted under AGPL.

If the project becomes materially valuable, the founder should consider registering the project name/logo trademarks in relevant jurisdictions.

---

## 8. GitHub organization model

### 8.1 Dedicated organization

The project shall live under a dedicated GitHub organization rather than the founder's personal repository namespace.

The organization can host this MCP project and future related open-source projects.

### 8.2 Creator funding vs repository identity

The organization hosts projects. The primary sponsorship identity remains the founder as an open-source creator across multiple projects.

Organization repositories may point `.github/FUNDING.yml` to:

- the founder's GitHub Sponsors profile;
- the founder's personal portfolio sponsorship/contact gateway.

### 8.3 Organization security

Required:

- organization-wide 2FA requirement;
- least-privilege roles;
- founder retains Owner role;
- very small number of organization Owners;
- protected/ruleset-controlled default branches;
- no direct pushes to protected main;
- required CI;
- required CLA status;
- required reviews;
- CODEOWNERS;
- restricted Actions/secrets permissions;
- restricted release/tag permissions;
- security-advisory access limited to trusted maintainers;
- periodic access review.

---

## 9. Governance model

The project is **founder-led open source**.

### 9.1 Founder

The founder has final authority over:

- project scope and vision;
- architecture;
- roadmap acceptance/rejection;
- release direction;
- security policy;
- repository/org governance;
- maintainer appointments/removals;
- trademark/brand use;
- license-policy changes subject to applicable contributor rights;
- sponsorship acceptance;
- development sponsorship acceptance;
- official communications.

The founder should seek community input when useful, but there is no binding community/sponsor voting mechanism.

### 9.2 Roles

```text
Founder
  |
Core Maintainers
  |
Maintainers
  |
Reviewers
  |
Contributors
```

Roles are permissions/responsibilities, not ownership.

### 9.3 Contributor

Any person/entity whose contribution is accepted under CLA.

No repository write authority by default.

### 9.4 Reviewer

Eligibility minimums:

- CLA covered;
- at least 3 months of constructive involvement;
- at least 5 meaningful merged contributions or equivalent sustained technical review/documentation/security contribution;
- demonstrated adherence to architecture/security/conduct;
- founder invitation.

Permissions are scoped; Reviewer status gives no default merge or secret access.

### 9.5 Maintainer

Eligibility minimums:

- at least 6 months of sustained involvement;
- at least 10 meaningful merged contributions/reviews with demonstrated quality;
- proven ability to review the assigned subsystem;
- reliable security/confidentiality conduct;
- 2FA enabled;
- founder appointment;
- acceptance of maintainer responsibilities in `MAINTAINERS.md`.

No one becomes Maintainer automatically by meeting numerical minimums. Founder acceptance is required.

Maintainer permissions are least-privilege and scope-specific through GitHub teams/CODEOWNERS.

### 9.6 Core Maintainer

Exceptional role requiring at minimum:

- 12 months sustained trusted involvement;
- broad architecture understanding;
- meaningful release/security/incident participation;
- strong review/mentorship record;
- founder appointment.

Core Maintainers may receive broad merge/release responsibilities but do not override Founder final governance authority.

### 9.7 Removal/reduction of permissions

Founder may remove or reduce project permissions for:

- security risk;
- inactivity where access is no longer needed;
- repeated quality failures;
- conduct violations;
- confidentiality/secret misuse;
- conflict of interest that creates project risk;
- governance abuse;
- compromised account.

Permission removal is not equivalent to revoking already-granted open-source/CLA rights.

### 9.8 Money cannot buy governance

Explicit rule:

```text
Sponsor != Reviewer
Sponsor != Maintainer
Sponsor != Core Maintainer
Development sponsor != roadmap authority
Consulting customer != project owner
```

A sponsor may also independently earn a community role through the same contribution/trust process as anyone else; the money itself is irrelevant to eligibility.

---

## 10. Contribution workflow

Required repository files:

```text
CONTRIBUTING.md
CLA.md
CODE_OF_CONDUCT.md
SECURITY.md
GOVERNANCE.md
MAINTAINERS.md
TRADEMARKS.md
```

Standard contribution flow:

1. issue/discussion where appropriate;
2. contributor reads contribution/security/architecture rules;
3. PR opened from a focused branch/fork;
4. CLA status passes;
5. CI passes;
6. CODEOWNERS/maintainer review;
7. security-sensitive changes receive additional review;
8. maintainer/founder merge according to branch rules;
9. changelog/release notes updated when user-visible.

Large architectural changes should use an issue/ADR proposal before implementation, but the founder may directly initiate them.

No contributor is guaranteed merge merely because a CLA was signed or work was performed.

---

## 11. Funding identity

### 11.1 Primary message

The top-level funding message is:

> **Sponsor my open-source work.**

The founder is building and maintaining multiple open-source projects over time. Sponsorship can support maintenance of this project, future related tools, infrastructure, documentation, research, and additional open-source creation.

### 11.2 Project-specific message

On this project's website/docs/repository:

> **Sponsor the continued development and maintenance of this open-source project.**

Corporate project-specific sponsorship may be earmarked by agreement, but the general personal GitHub Sponsors relationship should not falsely imply every dollar is legally restricted to one repository unless it actually is.

---

## 12. Funding channels

The sustainability model has four main lanes plus professional support later:

```text
1. Recurring/one-time sponsorship
2. Development sponsorship
3. Grants
4. Consulting/professional services
5. Separate future support/SLA agreements
```

These relationships must remain conceptually and contractually separate.

---

## 13. GitHub Sponsors

### 13.1 Primary platform

GitHub Sponsors is the primary public sponsorship mechanism at launch.

The project shall implement:

- founder GitHub Sponsors profile;
- `.github/FUNDING.yml` in organization repositories;
- README “Support Open Source Development” section;
- `SPONSORSHIP.md`;
- `SPONSORS.md` for opt-in recognition;
- personal portfolio link for corporate/special inquiries.

Jordan is listed as a supported region for receiving GitHub Sponsors funds in current GitHub documentation as of this specification date.

### 13.2 Suggested individual tiers

| Tier | Monthly amount | Purpose/recognition |
|---|---:|---|
| Supporter | $5 | Support ongoing OSS work |
| Backer | $10 | Support maintenance and new work |
| Builder | $25 | Name recognition if opted in |
| Maintainer Supporter | $50 | More prominent individual recognition if opted in |

One-time/custom amounts remain enabled where the platform permits.

No tier purchases software access.

### 13.3 Suggested company recurring tiers

| Tier | Monthly amount | Recognition |
|---|---:|---|
| Company Supporter | $100 | Optional company name |
| Bronze Sponsor | $250 | Optional logo on sponsors page |
| Silver Sponsor | $500 | Optional enhanced documentation/site recognition |
| Gold Sponsor | $1,000 | Optional prominent project/site recognition; eligible to request tightly controlled roadmap feedback session |
| Principal Sponsor | $2,500+ | Highest optional recognition; eligible to request tightly controlled roadmap feedback session |
| Custom | Custom | Negotiated sponsorship scope/recognition, never software entitlements |

Amounts can be adjusted over time without changing product architecture.

### 13.4 Sponsor benefits that are allowed

- opt-in name/logo/link recognition;
- sponsor page placement;
- public thank-you/release acknowledgment;
- development updates/newsletter if offered;
- ability to submit feature/use-case requests;
- eligibility at higher corporate tiers to request a pre-arranged roadmap/product feedback discussion;
- “Feature sponsored by Company A” attribution for accepted funded development.

### 13.5 Sponsor benefits that are prohibited

- exclusive/private product features;
- repository merge rights;
- maintainer status;
- roadmap voting power;
- guaranteed acceptance of requests;
- architectural veto;
- security embargo information beyond what a legitimate coordinated disclosure relationship requires;
- automatic consulting hours;
- SLA/response-time commitment;
- ownership of code/brand;
- competitor exclusion.

---

## 14. Sponsor communication policy

Higher-tier company sponsors may request limited direct product/roadmap feedback communication, but it is deliberately constrained.

Policy:

- request must be made through the designated portfolio/email channel;
- agenda/context must be provided in writing at least 7 calendar days before a requested meeting date;
- founder may accept, decline, reschedule, or request asynchronous discussion;
- eligible sponsors may normally request no more than one roadmap/feedback discussion per calendar quarter;
- recommended maximum meeting duration is 45 minutes;
- meeting is feedback/discussion, not support/SLA or roadmap commitment;
- production incidents/support requests are routed to consulting or a support agreement, not sponsor meetings;
- no sponsor receives an emergency/private messaging obligation by default.

This eligibility is a sponsor benefit, not a guaranteed service-level commitment.

---

## 15. Sponsor privacy and recognition

Recognition is **opt-in only**.

Default: sponsor identity/amount is not manually published by the project beyond what the sponsor platform itself makes public under its own settings.

Recognition options:

- anonymous/no listing;
- name only;
- name + link;
- company logo + link;
- feature-specific attribution when applicable.

Never publish personal donor details beyond what was explicitly authorized.

---

## 16. Development sponsorship

### 16.1 Purpose

A company/individual may offer to fund implementation of a specific capability that will remain part of the public open-source project.

### 16.2 Acceptance comes before funding commitment

Workflow:

```text
Sponsor proposes capability
          |
          v
Founder/maintainers evaluate
          |
      +---+---+
      |       |
    reject   accept in principle
              |
              v
        scope + estimate + terms
              |
              v
        funding agreement
              |
              v
       public implementation
              |
              v
         public release
```

A sponsor must not send money expecting a guaranteed feature before scope acceptance unless the sponsorship is explicitly unconditional/general support.

### 16.3 Acceptance criteria

Founder evaluates:

- alignment with product vision;
- architecture fit;
- security/privacy impact;
- long-term maintenance burden;
- usefulness beyond one proprietary customization;
- implementation feasibility;
- open-source/community value;
- dependency/license compatibility;
- available capacity.

Founder may reject a well-funded request for any of these reasons.

### 16.4 Output

Accepted sponsored functionality:

- is implemented in the public repository;
- uses normal review/testing/security rules;
- becomes available to every user;
- is not exclusive to sponsor;
- does not create a proprietary branch.

### 16.5 Attribution

Preferred public message, when sponsor opts in:

> **Feature sponsored by Company A**

The sponsorship amount is private by default and need not be displayed.

### 16.6 Sponsor does not own roadmap

Funding one feature does not give the sponsor priority/acceptance rights over subsequent requests.

---

## 17. Grants

The project may accept grants from companies, foundations, public-interest programs, research organizations, or other legitimate funders.

### 17.1 Unrestricted grants

Fund general open-source creation/maintenance with:

- no product benefit guarantee;
- no governance rights;
- no ownership;
- no exclusivity.

### 17.2 Scoped grants

May fund an accepted area such as:

- security;
- MCP interoperability;
- documentation;
- accessibility;
- testing;
- research;
- ecosystem tooling;
- specific public capabilities.

Terms must remain compatible with AGPL, contribution policy, public availability, and founder governance.

### 17.3 Grant transparency

Follow any legally/contractually required grant disclosure. Otherwise public amount disclosure is optional; acknowledgments can be opt-in/contractual.

---

## 18. Consulting and professional services

### 18.1 Separate from sponsorship

Consulting is billed **per engagement**.

A consulting client is purchasing defined professional work, not donating/sponsoring.

Potential services:

- architecture consulting;
- API-to-MCP readiness assessment;
- OpenAPI quality/improvement assessment;
- installation/deployment;
- enterprise environment integration;
- custom authentication integration;
- MCP security review;
- generated MCP review;
- upgrade/migration assistance;
- workshops/training;
- custom implementation that is compatible with project policy;
- operational consulting.

### 18.2 Engagement flow

```text
Inquiry
-> discovery/scope
-> written proposal/SOW
-> contract
-> invoice/payment terms
-> delivery
-> acceptance/close
```

The future company/entity may sign and invoice these contracts while project IP remains personally owned as described above.

### 18.3 Public project contributions from consulting

When consulting produces functionality suitable for the public project, the contract should permit contribution under the project license/CLA and should avoid granting the customer exclusive ownership over a core public feature.

Customer-specific confidential configuration/integration material may remain private where it is independent customer work and license obligations permit.

---

## 19. Future professional support agreements

The founder intends to eventually offer real support agreements with response-time/SLA commitments **under a separately negotiated communication and support contract**.

This is different from consulting and sponsorship.

A support agreement may define:

- customer contacts;
- authorized communication channels;
- supported versions/configurations;
- business hours/time zone;
- severity levels;
- first-response targets;
- escalation path;
- incident information requirements;
- included/excluded work;
- update/upgrade expectations;
- fees/payment;
- term/renewal/termination;
- service credits/limitations if agreed;
- security/confidentiality handling.

Do not promise an SLA through README text or sponsor tiers.

### 19.1 Relationship hierarchy

```text
Sponsorship
= fund open-source work

Consulting
= scoped work billed per engagement

Support agreement
= separately contracted ongoing response/support commitment
```

A company may have more than one relationship, but each must be explicit.

---

## 20. Funding milestones

Public sustainability goals should communicate what recurring funding enables, not fake expense precision.

Canonical milestones:

### $1,000/month — Sustainable side-hustle development

Funding meaning:

- covers meaningful project expenses;
- supports consistent maintenance/development alongside other work.

### $3,000/month — Part-time open-source development

Funding meaning:

- allows substantial dedicated part-time effort;
- more consistent maintenance, documentation, releases, and new capabilities.

### $5,000/month — Full-time open-source focus

Funding meaning:

- enables the founder to focus full-time on maintaining existing projects and creating new open-source software, subject to taxes/expenses/business reality.

### $10,000+/month — Grow supporting team capacity

Funding meaning:

- enables beginning to fund additional contributors/team capacity for development, security, testing, documentation, ecosystem work, or operations.

It does not promise an exact number of hires at exactly $10,000.

### 20.1 Funding display rules

If showing a funding total/goal, label whether it represents:

- gross sponsorship receipts;
- recurring monthly sponsorship;
- amount after platform fees;
- project-specific or creator-wide funding.

Do not imply every dollar is restricted to a project unless it is.

---

## 21. Personal portfolio gateway

The founder's personal portfolio is a parallel sponsorship/communication gateway.

Recommended sections:

```text
Open Source Projects
Sponsor My Work
Fund Development
Professional Services
Enterprise Support
Grants / Partnerships
Contact
```

Calls to action:

- GitHub Sponsors for simple recurring/one-time support;
- development sponsorship inquiry for funded public features;
- consulting inquiry for scoped professional work;
- support inquiry for future SLA agreements;
- grant/partnership contact.

The portfolio may handle lead/contact forms, but the MCP platform itself does not need a sponsor/payment subsystem.

---

## 22. Additional funding platforms

### 22.1 Launch phase

Keep the launch funding surface intentionally simple:

```text
Primary: GitHub Sponsors
Secondary: founder portfolio/contact/payment gateway as selected by founder
```

Do not add many competing donation platforms at once.

### 22.2 Open Collective later

Open Collective/fiscal hosting may be considered when there is meaningful need for:

- shared/community treasury;
- multiple maintainers/paid contributors;
- reimbursements;
- grants/corporate funding requiring fiscal administration;
- transparent project expenses;
- contractors;
- administrative/tax/invoicing support.

It is not required at initial launch.

### 22.3 Future company

Once the founder's legal company/entity exists, suitable corporate sponsorship, consulting, grants, and support payments may be contracted/received through it. This administrative arrangement does not grant the company automatic ownership of the open-source project IP.

---

## 23. Sponsorship messaging

Use language such as:

- Sponsor
- Support
- Back the project
- Fund open-source development
- Development sponsorship

Do not describe ordinary sponsorship as a tax-deductible charitable donation unless the receiving structure legally qualifies and the statement has been verified.

### 23.1 README message

The README should communicate:

- project remains open source;
- sponsorship helps fund maintenance, security, docs, infrastructure, research, and continued creation;
- individuals and companies may sponsor;
- core software is not paywalled;
- professional services are separate.

### 23.2 Corporate message

Recommended framing:

> If your organization relies on this project, consider sponsoring its continued maintenance and development or contact the founder about development sponsorship/professional services.

---

## 24. Sponsor policy boundaries

`SPONSORSHIP.md` must explicitly state:

> Sponsorship does not grant ownership, voting rights, maintainer status, architectural authority, roadmap control, feature guarantees, preferential security access, support SLAs, or exclusivity.

And:

> Funding may influence the amount of development capacity available, but never whether a public product feature is available to non-sponsors.

And:

> Feature requests associated with potential funding are accepted or rejected on project merit before a development sponsorship commitment is established.

---

## 25. Conflict-of-interest policy

Maintainers/reviewers must disclose material conflicts when reviewing a change directly connected to an employer/client/sponsor.

A company sponsor's employee may contribute normally under CLA, but:

- sponsor status does not bypass review;
- a contributor should not be sole approver for a sensitive change whose primary beneficiary/employer creates a material conflict;
- founder may require independent review;
- security/architecture rules remain identical.

---

## 26. Security disclosure and sponsors

Security reports follow `SECURITY.md` and coordinated disclosure process.

Sponsors do not receive early vulnerability information merely because they sponsor.

A support customer may receive security communications only under an explicit support/security-notification contract and appropriate coordinated-disclosure rules.

Do not expose private security advisory access to sponsors as a perk.

---

## 27. Required repository/governance files

Before public stable release, root/repository shall contain:

```text
LICENSE                       # AGPL-3.0-only
README.md
CONTRIBUTING.md
CLA.md
CODE_OF_CONDUCT.md
SECURITY.md
GOVERNANCE.md
MAINTAINERS.md
TRADEMARKS.md
SPONSORSHIP.md
SPONSORS.md
GENERATED_OUTPUTS.md
```

GitHub configuration:

```text
.github/
├── FUNDING.yml
├── CODEOWNERS
├── ISSUE_TEMPLATE/
├── PULL_REQUEST_TEMPLATE.md
└── workflows/
```

`PULL_REQUEST_TEMPLATE.md` reminds contributors that CLA coverage and CI/review are required.

---

## 28. `SPONSORS.md` rules

`SPONSORS.md` is recognition, not an accounting ledger.

Sections may include:

- Principal/Gold/Silver/Bronze corporate sponsors;
- development sponsors;
- individual supporter recognition;
- grant acknowledgments.

Only include people/organizations who opted in or whose agreement explicitly requires public attribution.

Do not publish private amounts unless explicitly authorized/required.

---

## 29. Long-term business model

The sustainable model is:

```text
Useful open-source projects
        |
        v
Adoption and community
        |
        +-----------------------------+
        |                             |
        v                             v
Individual sponsors            Corporate sponsors
        |                             |
        +----------+------------------+
                   |
                   v
        Development sponsorships
                   |
             Grants/partnerships
                   |
       Consulting engagements
                   |
       Support/SLA agreements
                   |
                   v
          More OSS capacity
                   |
                   v
     Maintenance + new projects
```

The business does not depend on restricting the software itself.

---

## 30. What is explicitly prohibited

Unless the founder revises this document, do not introduce:

- DCO contribution requirements;
- copyright assignment requirement for ordinary community contributions;
- proprietary dual-license offering;
- sponsor-only/private feature edition;
- paid entitlements in the application;
- sponsor-based runtime limits;
- sponsor roadmap votes;
- automatic sponsor support hours;
- automatic sponsor SLA;
- sale of maintainer status;
- hidden corporate architecture veto;
- mandatory publication of private sponsor amounts;
- automatic transfer of founder IP to a future company;
- claims that commercial use itself is forbidden by the AGPL project license.

---

## 31. Launch checklist

### Legal/governance

- [ ] `LICENSE` contains AGPL-3.0-only text.
- [ ] Founder copyright/trademark ownership records are retained.
- [ ] Lawyer-reviewed ICLA/CCLA wording consistent with this policy is published.
- [ ] CLA Assistant is configured and required.
- [ ] No DCO check/workflow exists.
- [ ] `CONTRIBUTING.md`, `GOVERNANCE.md`, `MAINTAINERS.md`, `SECURITY.md`, `TRADEMARKS.md`, and `GENERATED_OUTPUTS.md` are published.

### GitHub organization

- [ ] Dedicated organization hosts repository.
- [ ] 2FA requirement enabled.
- [ ] branch/ruleset protections enabled.
- [ ] CI + CLA + review checks required.
- [ ] CODEOWNERS configured.
- [ ] secrets/releases/security permissions restricted.

### Sponsorship

- [ ] GitHub Sponsors profile active.
- [ ] `.github/FUNDING.yml` configured.
- [ ] README support section published.
- [ ] `SPONSORSHIP.md` published.
- [ ] `SPONSORS.md` opt-in process defined.
- [ ] portfolio funding/contact gateway linked.
- [ ] funding milestones communicated accurately if published.

### Commercial relationships

- [ ] consulting is described as per-engagement work, separate from sponsorship.
- [ ] development sponsorship request/acceptance process is published.
- [ ] grants pathway/contact exists.
- [ ] no SLA is advertised until the actual support agreement offering/contracts are ready.

---

## 32. Completion criteria

This model is implemented correctly when all of the following are true:

1. public source is AGPL-3.0-only;
2. external contributions require CLA and no DCO mechanism is required;
3. contributor copyright is retained while CLA grants required project rights;
4. founder-authored IP/trademarks remain personally owned unless explicitly transferred;
5. future company role is contracts/payments/services, not automatic IP ownership;
6. no proprietary commercial-license exception or open-core feature split exists;
7. generated-output/user-input policy is published;
8. GitHub organization security/maintainer rules enforce founder-led least privilege;
9. sponsor recognition is opt-in;
10. GitHub Sponsors is the primary public funding channel and portfolio is the secondary communication/funding gateway;
11. development sponsorship can fund only founder-accepted public features and public attribution can say “Feature sponsored by Company A” without requiring amount disclosure;
12. grants are allowed without governance/product entitlements;
13. consulting is billed per engagement;
14. future support/SLA is a separately contracted relationship with defined communications/response terms;
15. funding milestones communicate $1k side-hustle, $3k part-time, $5k full-time, and $10k+ team-capacity outcomes;
16. the application contains no sponsor/subscription/billing/entitlement enforcement;
17. sponsors cannot purchase governance, maintainer access, roadmap control, or hidden security access.

---

## 33. Reference baseline

The project should periodically re-check official sources before changing policy or tooling, including:

- GNU/OSI AGPL-3.0 license text and interpretation baseline;
- GitHub Sponsors eligibility/fees/FUNDING.yml documentation;
- GitHub organization security/ruleset documentation;
- CLA Assistant GitHub App documentation/status;
- established ICLA/CCLA examples such as Apache/Harmony/other reputable projects for legal-review input.

This specification is project policy, not individualized legal/tax/accounting advice. Legal documents, trademark filings, tax treatment, corporate contracts, and SLAs should be reviewed by qualified professionals before they are relied on commercially.
