# Real-model 2x2 ablation (retrieval x prompt)

Specialty-stratified sample: 10 questions; repair budget: k=3.
Systems: A=boundary+SHACL / C=boundary+naive / D=naive+SHACL / B=naive+naive.

| Model | First pass A/C/D/B | Converged A/C/D/B | Hallucination A/C/D/B |
|---|---:|---:|---:|
| qwen3:8b | 90%/0%/100%/0% | 100%/20%/100%/40% | 0.00/0.00/0.00/0.00 |
| llama3.1:8b | 100%/0%/100%/0% | 100%/20%/100%/60% | 0.47/0.00/0.13/0.10 |
| gemma3:4b | 50%/0%/30%/0% | 60%/0%/30%/0% | 0.00/0.00/0.00/0.00 |
