"""
verify_chunk7.py
Run: python verify_chunk7.py
Feeds a dense health insurance policy clause and prints simplified explanation.
Set GEMINI_API_KEY or OPENAI_API_KEY in .env to use a real LLM.
Falls back to mock mode automatically if no key is set.
"""

from src.assistant.explainer import explain_document, SUPPORTED_LANGUAGES

INSURANCE_CLAUSE = """
SECTION 4.2 — EXCLUSIONS AND LIMITATIONS:
The Company shall not be liable to make any payment under this policy in respect of
any expenses whatsoever incurred by any insured person in connection with or in
respect of: (a) Pre-existing Diseases as defined in the policy, until 48 continuous
months of coverage have elapsed since inception of the first policy; (b) Any disease
contracted by the insured within the first 30 days of the commencement of the policy,
except for accidental injuries; (c) Maternity expenses including caesarean section,
unless the insured has completed a waiting period of 9 months; (d) Dental treatment
or surgery of any kind unless requiring hospitalisation; (e) Expenses arising from
self-inflicted injuries, suicide attempts, or participation in hazardous activities
including but not limited to mountaineering, racing, or skydiving.

SECTION 5.1 — PREMIUM REVISION CLAUSE:
The insurer reserves the right to revise the premium rates at each renewal based on
claims experience, medical inflation index, and regulatory directives from IRDAI.
The insured shall be notified 30 days prior to renewal. Failure to pay revised
premiums within the grace period of 15 days shall result in automatic policy lapse
and forfeiture of all accumulated no-claim bonuses. A reinstatement fee of 2% of
the annual premium shall apply for policies lapsed beyond 90 days.

SECTION 6.3 — LOCK-IN AND SURRENDER:
This policy carries a mandatory lock-in period of 36 months. Partial or full
surrender during the lock-in period shall attract a discontinuance charge of 4%
on the fund value or Rs. 6,000, whichever is lower. Processing and administrative
fees of 2% on the sum assured are non-refundable under any circumstances.
"""


def print_result(result, title: str) -> None:
    print(f"\n{'='*60}")
    print(f"  {title}  [Provider: {result.provider}]")
    print(f"{'='*60}")

    print("\n📋 SIMPLE SUMMARY (5th-grade level):")
    for i, point in enumerate(result.summary, 1):
        print(f"  {i}. {point}")

    print("\n⚠️  THINGS TO WATCH OUT FOR:")
    for i, point in enumerate(result.watch_out, 1):
        print(f"  {i}. {point}")

    if result.translation:
        print(f"\n🌐 TRANSLATION ({result.language.upper()}):")
        print(f"  {result.translation}")


def main():
    print("\n🏥 FinGuard AI — Document Explainer & Jargon Buster")
    print("Analyzing health insurance policy clause...\n")

    # Test 1: English only
    result_en = explain_document(INSURANCE_CLAUSE, provider="auto")
    print_result(result_en, "English Explanation")

    # Test 2: With Hindi translation
    result_hi = explain_document(INSURANCE_CLAUSE, language="hindi", provider="auto")
    print_result(result_hi, "With Hindi Translation")

    # Test 3: With Spanish translation
    result_es = explain_document(INSURANCE_CLAUSE, language="spanish", provider="auto")
    print_result(result_es, "With Spanish Translation")

    print(f"\n{'='*60}")
    print(f"  Supported languages: {', '.join(SUPPORTED_LANGUAGES.keys())}")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
