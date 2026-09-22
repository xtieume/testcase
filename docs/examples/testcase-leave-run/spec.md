# SPEC: Annual leave deduction (FEEC HR, v2)

R1  An employee's annual balance is granted on the joining anniversary: 12 days for
    service < 3 years, 16 days for >= 3 years, 20 days for >= 6 years.
R2  A leave request deducts from the balance in 0.5-day units. Half days are AM or PM.
R3  A request spanning a public holiday does not deduct for that day.
R4  Balance may not go below 0. A request exceeding the balance is rejected.
R5  Unused days expire 3 months after the next anniversary. Expired days cannot be restored.
R6  Only the employee's direct manager may approve. Approval after the leave start date
    is allowed but must be flagged.
R7  A cancelled request restores the deducted days, unless those days have already expired
    under R5.
