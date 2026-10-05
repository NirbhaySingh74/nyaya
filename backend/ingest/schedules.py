"""Schedules whose PDF extraction is unusable (tables split into columns, OCR'd
footnote markers). Transcribed from the same source PDFs in data/raw/."""

DPDP_SCHEDULE = """THE SCHEDULE [See section 33(1)] — Penalties for breach of provisions of this Act or rules made thereunder.
1. Breach in observing the obligation of Data Fiduciary to take reasonable security safeguards to prevent personal data breach under sub-section (5) of section 8. Penalty: may extend to two hundred and fifty crore rupees.
2. Breach in observing the obligation to give the Board or affected Data Principal notice of a personal data breach under sub-section (6) of section 8. Penalty: may extend to two hundred crore rupees.
3. Breach in observance of additional obligations in relation to children under section 9. Penalty: may extend to two hundred crore rupees.
4. Breach in observance of additional obligations of Significant Data Fiduciary under section 10. Penalty: may extend to one hundred and fifty crore rupees.
5. Breach in observance of the duties under section 15. Penalty: may extend to ten thousand rupees.
6. Breach of any term of voluntary undertaking accepted by the Board under section 32. Penalty: up to the extent applicable for the breach in respect of which the proceedings under section 28 were instituted.
7. Breach of any other provision of this Act or the rules made thereunder. Penalty: may extend to fifty crore rupees."""

RTI_FIRST_SCHEDULE = """THE FIRST SCHEDULE [See sections 13(3) and 16(3)] — Form of oath or affirmation to be made by the Chief Information Commissioner, the Information Commissioner, the State Chief Information Commissioner or the State Information Commissioner.
"I, ....., having been appointed Chief Information Commissioner/Information Commissioner/State Chief Information Commissioner/State Information Commissioner swear in the name of God / solemnly affirm that I will bear true faith and allegiance to the Constitution of India as by law established, that I will uphold the sovereignty and integrity of India, that I will duly and faithfully and to the best of my ability, knowledge and judgment perform the duties of my office without fear or favour, affection or ill-will and that I will uphold the Constitution and the laws.\""""

RTI_SECOND_SCHEDULE = """THE SECOND SCHEDULE (See section 24) — Intelligence and security organisations established by the Central Government, to which the Act does not apply (except for information pertaining to allegations of corruption and human rights violations).
1. Intelligence Bureau.
2. Research and Analysis Wing including its technical wing namely, the Aviation Research Centre of the Cabinet Secretariat.
3. Directorate of Revenue Intelligence.
4. Central Economic Intelligence Bureau.
5. Directorate of Enforcement.
6. Narcotics Control Bureau.
7. (Omitted.)
8. Special Frontier Force.
9. Border Security Force.
10. Central Reserve Police Force.
11. Indo-Tibetan Border Police.
12. Central Industrial Security Force.
13. National Security Guards.
14. Assam Rifles.
15. Sashastra Seema Bal.
16. Directorate General of Income-tax (Investigation).
17. National Technical Research Organisation.
18. Financial Intelligence Unit, India.
19. Special Protection Group.
20. Defence Research and Development Organisation.
21. Border Road Development Board.
22. National Security Council Secretariat.
23. Central Bureau of Investigation.
24. National Investigation Agency.
25. National Intelligence Grid.
26. Strategic Forces Command."""

SCHEDULES = {
    "dpdp": [("Schedule", "The Schedule — Penalties", DPDP_SCHEDULE)],
    "rti": [
        ("First Schedule", "The First Schedule — Form of oath or affirmation", RTI_FIRST_SCHEDULE),
        ("Second Schedule", "The Second Schedule — Exempt intelligence and security organisations", RTI_SECOND_SCHEDULE),
    ],
    "cpa": [],
}
