CREATE DATABASE IF NOT EXISTS placement_career;
USE placement_career;

CREATE TABLE users (
  id INT AUTO_INCREMENT PRIMARY KEY,
  name VARCHAR(120) NOT NULL,
  email VARCHAR(190) NOT NULL UNIQUE,
  password_hash VARCHAR(255) NOT NULL,
  created_at VARCHAR(40) NOT NULL
);

CREATE TABLE student_profiles (
  id INT AUTO_INCREMENT PRIMARY KEY,
  user_id INT NOT NULL UNIQUE,
  degree VARCHAR(100) NOT NULL,
  cgpa DECIMAL(4,2) NOT NULL DEFAULT 0,
  backlogs INT NOT NULL DEFAULT 0,
  projects INT NOT NULL DEFAULT 0,
  internships INT NOT NULL DEFAULT 0,
  coding INT NOT NULL DEFAULT 0,
  communication INT NOT NULL DEFAULT 0,
  sql_score INT NOT NULL DEFAULT 0,
  web INT NOT NULL DEFAULT 0,
  problem_solving INT NOT NULL DEFAULT 0,
  university VARCHAR(190) NOT NULL DEFAULT 'University of Mumbai',
  stream VARCHAR(100) NOT NULL DEFAULT 'Science',
  preferred_role VARCHAR(100) NOT NULL DEFAULT 'Data Analyst',
  tenth_percentage DECIMAL(5,2) NOT NULL DEFAULT 0,
  twelfth_percentage DECIMAL(5,2) NOT NULL DEFAULT 0,
  resume_filename VARCHAR(255) NOT NULL DEFAULT '',
  resume_text LONGTEXT,
  resume_skills JSON,
  coding_languages JSON,
  resume_strengths JSON,
  ats_score INT NOT NULL DEFAULT 0,
  FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE TABLE assessments (
  id INT AUTO_INCREMENT PRIMARY KEY,
  user_id INT NOT NULL,
  aptitude_score INT NOT NULL,
  section_scores JSON NOT NULL,
  features_json JSON NOT NULL,
  predicted_probability DECIMAL(6,5) NOT NULL,
  predicted_label VARCHAR(40) NOT NULL,
  proctor_events JSON NOT NULL,
  created_at VARCHAR(40) NOT NULL,
  FOREIGN KEY (user_id) REFERENCES users(id)
);
