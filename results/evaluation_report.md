# Evaluation report

Model: `gemini-3.5-flash-lite`

| Metric | Result |
| --- | --- |
| Test cases | 25 |
| Cases fully correct | 22 of 25 |
| Status accuracy | 92.0% |
| Field accuracy | 99.2% |
| Missing fields left as null | 99.3% |
| Invented values | 2 |
| API or schema failures | 0 |

## By category

| Category | Cases | Fully correct | Status accuracy | Field accuracy | Invented values |
| --- | --- | --- | --- | --- | --- |
| complete | 7 | 6 | 100.0% | 99.1% | 0 |
| missing_info | 7 | 7 | 100.0% | 100.0% | 0 |
| ambiguous | 5 | 3 | 60.0% | 97.5% | 2 |
| invalid | 6 | 6 | 100.0% | 100.0% | 0 |

## Cases that were not fully correct

### complete_05: Experience written as a word
- `location`: expected `Lisbon`, got `None`

### ambiguous_02: Two different names
- Status: expected `ambiguous`, got `valid`
- `applicant_name`: expected `None`, got `Marco Conti`

### ambiguous_03: Vague experience
- Status: expected `ambiguous`, got `valid`
- `current_job_title`: expected `None`, got `teacher`

