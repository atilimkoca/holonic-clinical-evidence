# Neo4J status

No Neo4J server was reachable during this run, so only the import + query Cypher scripts were generated under results/neo4j/. These scripts are portability artifacts outside the measured benchmark; the reported query timings are the per-query SPARQL timings (rdflib) in results/expressiveness.csv. To execute them: start Neo4J with n10s, set NEO4J_URI/USER/PASS, then `cypher-shell -f results/neo4j/import_holonic.cypher` and re-run this module.
