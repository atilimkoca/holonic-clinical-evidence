// S05_drugs_treating_htn
MATCH (x:Drug)-[:TREATS]->(:Disease {id:'hypertension'}) RETURN x.id;

// M01_treats_confidence
MATCH (x:Drug)-[t:TREATS]->(d:Disease) RETURN x.id, d.id, t.confidence;

// M03_high_conf_pairs
MATCH (x:Drug)-[t:TREATS]->(d:Disease) WHERE t.confidence > 0.9 RETURN x.id, d.id;

// C08_drug_breadth
MATCH (x:Drug)-[t:TREATS]->(d:Disease) WHERE t.confidence >= 0.85 RETURN x.id, count(DISTINCT d) AS n ORDER BY n DESC LIMIT 5;
