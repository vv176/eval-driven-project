"""
AskCorp — synthetic 4-index corpus for the agentic-RAG teaching demo.

Four knowledge bases, each a separate Weaviate collection. The documents are
deliberately engineered so a good agent's *decisions* pay off:

  - routing to ONE index            (e.g. a pure HR question)
  - fan-out across TWO indexes      (refund POLICY in Product + HOW-TO in Eng-wiki)
  - adaptive-K re-query             (the reorg decision is buried among many
                                     "Q3 / team / quarter" announcement distractors)
  - strategy choice (bm25)          (a policy *code* HR-CL-12 — exact-token match)
  - query rewriting                 (announcement says "reorganization / merge",
                                     user says "restructuring" — wording differs)
  - multi-query variations          (a broad "new joiner perks" ask spans several
                                     distinct HR docs)
"""

# index_key -> human description (used in the agent's system prompt + tool enum)
INDEXES = {
    "HR": (
        "Internal HR policies: casual / sick / earned leave, work-from-home, "
        "expense reimbursement, health benefits, referral bonus. Policies carry "
        "a code like HR-CL-12."
    ),
    "ENG_WIKI": (
        "Engineering how-to wiki — step-by-step INTERNAL procedures: issuing a "
        "refund in the Admin Panel, requesting admin access, deploying a service, "
        "on-call, feature flags, DB migrations."
    ),
    "PRODUCT": (
        "Customer-facing product documentation & POLICIES: refund policy, "
        "pricing/plans, SLA, data privacy, free trial, cancellation."
    ),
    "ANNOUNCEMENTS": (
        "Dated company announcements & decisions: town halls, holidays, "
        "reorganizations, leadership changes, OKRs, events."
    ),
}

# collection_key -> list of {id, text}
CORPUS = {
    "HR": [
        {
            "id": "hr_casual_leave",
            "text": (
                "Casual Leave (policy code HR-CL-12): every full-time employee "
                "receives 12 casual leave days per calendar year, accrued one per "
                "month. Casual leave is for short, unplanned personal absences. "
                "Unused casual leave lapses at year end and cannot be carried over."
            ),
        },
        {
            "id": "hr_sick_leave",
            "text": (
                "Sick Leave (policy code HR-SL-08): 10 paid sick days per year. A "
                "doctor's certificate is required for any sick absence longer than "
                "two consecutive days."
            ),
        },
        {
            "id": "hr_earned_leave",
            "text": (
                "Earned / Privilege Leave (policy code HR-EL-18): 18 days per year, "
                "carry-over allowed up to a maximum balance of 30 days. Encashment "
                "is permitted only at exit."
            ),
        },
        {
            "id": "hr_wfh",
            "text": (
                "Work-from-home: employees may work remotely up to two days per "
                "week with manager approval. Fully remote arrangements require VP "
                "sign-off and a home-office stipend request."
            ),
        },
        {
            "id": "hr_expense",
            "text": (
                "Expense reimbursement: submit claims within 30 days through the "
                "Expenses portal. Domestic meals are capped at 40 dollars per day; "
                "international travel uses per-diem rates."
            ),
        },
        {
            "id": "hr_referral",
            "text": (
                "Employee referral bonus: you earn a 2000 dollar referral bonus "
                "once a candidate you referred is hired and completes 90 days of "
                "employment. New joiners are also eligible to refer from day one."
            ),
        },
        {
            "id": "hr_benefits",
            "text": (
                "Health benefits: the company health plan covers the employee, a "
                "spouse, and up to two children. Dental coverage was added to the "
                "plan in 2024."
            ),
        },
    ],
    "ENG_WIKI": [
        {
            "id": "eng_refund_howto",
            "text": (
                "How to issue a refund in the Admin Panel: open Admin Panel then "
                "Billing then Transactions, search for the customer's charge, click "
                "Refund, choose full or partial, and confirm. Refunds settle in "
                "5 to 7 business days. You need the billing.refund permission."
            ),
        },
        {
            "id": "eng_admin_access",
            "text": (
                "Requesting Admin Panel access: file an access request in the IT "
                "portal. Billing roles such as billing.refund additionally require "
                "manager and finance approval before they are granted."
            ),
        },
        {
            "id": "eng_deploy",
            "text": (
                "Deploying a service: merge to main, let CI build the artifact, "
                "approve the release in Spinnaker, then watch the canary for 15 "
                "minutes before promoting to 100 percent."
            ),
        },
        {
            "id": "eng_oncall",
            "text": (
                "On-call runbook: the PagerDuty rotation is weekly. Acknowledge "
                "pages within 5 minutes; if unacknowledged, the alert escalates to "
                "the secondary on-call after 15 minutes."
            ),
        },
        {
            "id": "eng_feature_flags",
            "text": (
                "Toggling a feature flag: use the LaunchControl dashboard. A staged "
                "rollout is recommended: 1 percent, then 25 percent, then 100 "
                "percent, watching error rates at each step."
            ),
        },
        {
            "id": "eng_db_migration",
            "text": (
                "Running a database migration: always take a snapshot first, run "
                "the migration through the migration runner, and schedule it during "
                "off-peak hours to limit lock contention."
            ),
        },
    ],
    "PRODUCT": [
        {
            "id": "prod_refund_policy",
            "text": (
                "Refund policy: customers may request a full refund within 14 days "
                "of purchase. After 14 days, only annual plans qualify for a "
                "prorated refund. Add-ons and one-time fees are non-refundable."
            ),
        },
        {
            "id": "prod_pricing",
            "text": (
                "Pricing: we offer Free, Pro at 12 dollars per month, Business at "
                "30 dollars per user per month, and Enterprise with custom pricing."
            ),
        },
        {
            "id": "prod_sla",
            "text": (
                "Service level agreement: Business and Enterprise plans include a "
                "99.9 percent uptime SLA. If we miss it, customers receive service "
                "credits on the next invoice."
            ),
        },
        {
            "id": "prod_privacy",
            "text": (
                "Data privacy: customer data is encrypted at rest using AES-256. "
                "Account deletion requests are honored within 30 days, after which "
                "data is irreversibly purged."
            ),
        },
        {
            "id": "prod_trial",
            "text": (
                "Free trial: new users get a 14-day Pro trial with no credit card "
                "required. At the end of the trial the account converts to the Free "
                "plan unless the user upgrades."
            ),
        },
        {
            "id": "prod_cancellation",
            "text": (
                "Cancellation: customers can downgrade or cancel anytime under "
                "Settings then Billing. Paid access continues until the end of the "
                "current billing period."
            ),
        },
    ],
    "ANNOUNCEMENTS": [
        # The reorg DECISION is the needle. It avoids the words "restructuring"
        # and "reorg" (uses "reorganization / merge / org structure") so a literal
        # query won't keyword-match — rewarding rewrite / vector / wider K. It is
        # surrounded by many "Q3 / team / quarter / change" distractors.
        {
            "id": "ann_reorg_decision",
            "text": (
                "[2025-07-18] Org update: effective this quarter, the Platform and "
                "Infrastructure teams will merge into a single Core Engineering "
                "organization led by VP Aisha Khan. Reporting lines change on "
                "September 1. The Payments team moves under Product. This "
                "reorganization involves no headcount reductions."
            ),
        },
        {
            "id": "ann_q3_okrs",
            "text": (
                "[2025-07-15] Q3 OKRs are published. The company-wide focus this "
                "quarter is reliability and onboarding activation. Each team should "
                "align its quarterly goals accordingly."
            ),
        },
        {
            "id": "ann_townhall",
            "text": (
                "[2025-07-02] The July town hall recording is now posted. Topics "
                "covered include the product roadmap, a hiring update, and the "
                "office reopening plan for the quarter."
            ),
        },
        {
            "id": "ann_newcfo",
            "text": (
                "[2025-07-10] Leadership change: please welcome our new Chief "
                "Financial Officer, Ramesh Iyer, who joins us this quarter from a "
                "fintech background."
            ),
        },
        {
            "id": "ann_office_move",
            "text": (
                "[2025-09-05] The Bangalore office will relocate to a larger space "
                "in Whitefield in October. Seating teams and move logistics will be "
                "shared closer to the date."
            ),
        },
        {
            "id": "ann_hackathon",
            "text": (
                "[2025-08-01] Registration for the Q3 hackathon is open. Form teams "
                "of up to four people; the theme this quarter is internal developer "
                "productivity."
            ),
        },
        {
            "id": "ann_security_training",
            "text": (
                "[2025-07-25] Annual security training is due by August 31. Please "
                "complete the updated modules in the LMS before the deadline."
            ),
        },
        {
            "id": "ann_holiday",
            "text": (
                "[2025-08-10] Reminder: Independence Day is a company holiday on "
                "August 15. All offices will be closed and support runs on a "
                "skeleton on-call rota."
            ),
        },
        {
            "id": "ann_benefits_update",
            "text": (
                "[2025-06-20] Benefits update: dental coverage is now included in "
                "the company health plan starting next enrollment cycle."
            ),
        },
        {
            "id": "ann_parking",
            "text": (
                "[2025-08-22] New parking allocation for the quarter: badge access "
                "to level 2 is being reassigned by team; check your updated parking "
                "zone in the facilities app."
            ),
        },
        # --- near-miss distractors that crowd out the reorg DECISION at small K ---
        {
            "id": "ann_team_survey",
            "text": (
                "[2025-07-20] The quarterly team-health survey is now open. Tell us "
                "how your team is doing on collaboration, workload, and team "
                "structure this quarter. Your feedback shapes how we run teams."
            ),
        },
        {
            "id": "ann_allhands_followup",
            "text": (
                "[2025-07-22] Follow-up from the all-hands about upcoming team "
                "changes this quarter: your manager will walk you through what the "
                "changes mean for your team in your next one-on-one."
            ),
        },
        {
            "id": "ann_seating_reorg",
            "text": (
                "[2025-08-15] Seating refresh: desks for several teams will be "
                "reorganized across floors this quarter to put collaborating teams "
                "closer together. This is a seating change only — no team or "
                "reporting changes are implied."
            ),
        },
    ],
}


def collection_name(index_key: str) -> str:
    return f"AskCorp_{index_key}"
