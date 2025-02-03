
ALTER TABLE ELN_WRITEUP_COMPARISON 
DROP CONSTRAINT eln_writeup_comparison_exp_id_system_name_1_fkey,
DROP CONSTRAINT eln_writeup_comparison_exp_id_system_name_2_fkey;

ALTER TABLE ELN_WRITEUP_API_EXTRACT 
DROP CONSTRAINT eln_writeup_api_extract_pkey;

ALTER TABLE ELN_WRITEUP_API_EXTRACT 
ADD COLUMN analysis_date DATE NOT NULL DEFAULT '2024-01-30';

ALTER TABLE ELN_WRITEUP_API_EXTRACT 
ADD PRIMARY KEY (exp_id, system_name, analysis_date);

ALTER TABLE ELN_WRITEUP_COMPARISON 
ADD COLUMN analysis_date DATE NOT NULL DEFAULT '2024-01-30';

ALTER TABLE ELN_WRITEUP_COMPARISON 
DROP CONSTRAINT eln_writeup_comparison_pkey;

ALTER TABLE ELN_WRITEUP_COMPARISON 
ADD PRIMARY KEY (exp_id, system_name_1, system_name_2, analysis_date);

ALTER TABLE ELN_WRITEUP_COMPARISON 
ADD CONSTRAINT eln_writeup_comparison_exp_id_system_name_1_fkey 
FOREIGN KEY (exp_id, system_name_1, analysis_date) 
REFERENCES ELN_WRITEUP_API_EXTRACT (exp_id, system_name, analysis_date),

ADD CONSTRAINT eln_writeup_comparison_exp_id_system_name_2_fkey 
FOREIGN KEY (exp_id, system_name_2, analysis_date) 
REFERENCES ELN_WRITEUP_API_EXTRACT (exp_id, system_name, analysis_date);
