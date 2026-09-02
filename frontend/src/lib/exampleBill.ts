/**
 * One real bill, so a first-time visitor is one click from a working audit.
 *
 * Copied verbatim from eval/bills/B01 - the same fixture the evaluation scores
 * and the same text the paste box would receive. B01 is the room-rent breach:
 * Rs 8,000 a day against a Rs 5,000 limit, which is the case worth showing,
 * because it is the one where a single capped line quietly rewrites four
 * others.
 *
 * tests/test_example_bill.py fails if any of this drifts from the fixture.
 * Regenerate rather than hand-edit.
 */
export interface ExampleBill {
  id: string;
  text: string;
  policy: string;
  sumInsured: number;
  policyStartDate: string;
  admissionDate: string;
}

export const EXAMPLE_BILL: ExampleBill = {
  id: "B01",
  policy: "star_health",
  sumInsured: 300000,
  policyStartDate: "2022-06-15",
  admissionDate: "2026-03-12",
  text: "CITY CARE MULTISPECIALITY HOSPITAL\nChennai - 600 034\n\nPatient Name: Ramesh Kumar\nUHID: B01500\nPhone: 9876543210\nAdmission: 2026-03-12    Discharge: 2026-03-17\n\n--------------------------------------------------------------\nDESCRIPTION                                   QTY       AMOUNT\n--------------------------------------------------------------\nRoom Rent (Single A/C) 8,000 x 5 days           5    40,000.00\nICU Charges 12,000 x 2 days                     2    24,000.00\nSurgeon Fee                                     1    80,000.00\nAnaesthetist Charges                            1    15,000.00\nMedicines and Drugs                             1    38,000.00\nOperation Theatre Charges                       1    22,000.00\nInvestigations - CT and Bloodwork               1    14,000.00\nSurgical Gloves                                20     1,200.00\nDisposable Syringes                            40       800.00\nAmbulance Charges                               1     1,000.00\n--------------------------------------------------------------\nGRAND TOTAL                                         236,000.00\n--------------------------------------------------------------",
};
