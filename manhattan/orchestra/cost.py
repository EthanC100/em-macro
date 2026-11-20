"""Compute-cost estimates against the monthly research budget (about S$500).

Workloads are **measured** figures from this repository; prices are **assumptions** (third-party trackers and
provider pages read on 2026-11-19, not quotes; check them before renting anything). The orchestrator never rents,
starts or pays for anything: these numbers only size ``limits.monthly_vcpu_hours`` and ``price_sgd_per_vcpu_hour``.
Sources and reasoning: docs/manhattan/orchestra/OPERATIONS.md section 7.
"""
from __future__ import annotations

USD_SGD = 1.29              # assumption: about 1.28-1.29 mid-market, mid-November 2026
EUR_SGD = 1.42              # assumption: about 1.42 mid-market, mid-November 2026
HOURS_PER_MONTH = 730

# measured workloads (CPU-hours or reserved vCPU-hours)
WORKLOADS = {
    "hte_1m_full": {"vcpu_h": 0.492, "source": "docs/manhattan/hte/BENCHMARKS.md section 6 (443 s on 4 vCPU)"},
    "hte_1m_stage1": {"vcpu_h": 0.218, "source": "BENCHMARKS.md section 2 (195.9 s on 4 vCPU)"},
    "sim_development_programme": {"vcpu_h": 2200.0, "source": "docs/manhattan/SIM_RUNBOOK.md section 1 "
                                                             "(2,000-2,200 CPU-hours; upper end used)"},
}

# price assumptions, SGD per vCPU-hour, and fixed monthly costs
OPTIONS = {
    "owned_hardware": {"sgd_per_vcpu_h": 0.0, "fixed_sgd_month": 0.0, "vcpus": 8,
                       "note": "the iMac or another machine already owned: no marginal spend (electricity aside)"},
    "github_public_runners": {"sgd_per_vcpu_h": 0.0, "fixed_sgd_month": 0.0, "vcpus": 4 * 20,
                              "note": "free for a public repository; logs and artifacts are public; 6 h per job; "
                                      "synthetic work only (manhattan-sim.yml already does this, by hand, from main)"},
    "hetzner_ax42_dedicated": {"sgd_per_vcpu_h": 0.0, "fixed_sgd_month": round(97.30 * EUR_SGD, 2), "vcpus": 16,
                               "setup_sgd": round(49 * EUR_SGD, 2),
                               "note": "flat monthly rent (EUR 97.30 excl. VAT after the June 2026 adjustment, "
                                       "8 cores / 16 threads); every hour of the month is paid whether used or not"},
    "aws_c7a_2xlarge_on_demand": {"sgd_per_vcpu_h": round(0.4106 / 8 * USD_SGD, 4), "fixed_sgd_month": 0.0,
                                  "vcpus": 8, "note": "US$0.4106/h for 8 vCPU, us-east-1, per-second billing; "
                                                      "storage and egress extra"},
    "aws_c7a_2xlarge_spot": {"sgd_per_vcpu_h": round(0.19 / 8 * USD_SGD, 4), "fixed_sgd_month": 0.0, "vcpus": 8,
                             "note": "about US$0.16-0.19/h; interruptions are ordinary resumes here (HTE refuses a "
                                     "resume in another numerical environment, so pin the instance type)"},
}


def monthly(option: str, vcpu_h: float) -> dict:
    o = OPTIONS[option]
    variable = vcpu_h * o["sgd_per_vcpu_h"]
    wall_h = vcpu_h / o["vcpus"]
    return {"option": option, "vcpu_h": vcpu_h, "sgd": round(o["fixed_sgd_month"] + variable, 2),
            "wall_hours_at_full_use": round(wall_h, 1), "fits_one_month": wall_h <= HOURS_PER_MONTH,
            "note": o["note"]}


def table(vcpu_h: float) -> list[dict]:
    return [monthly(k, vcpu_h) for k in OPTIONS]


def vcpu_hours_for_budget(option: str, budget_sgd: float = 500.0) -> float | None:
    o = OPTIONS[option]
    if o["sgd_per_vcpu_h"] == 0:
        return None if o["fixed_sgd_month"] <= budget_sgd else 0.0
    return max(0.0, (budget_sgd - o["fixed_sgd_month"]) / o["sgd_per_vcpu_h"])
