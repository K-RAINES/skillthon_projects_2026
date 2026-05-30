# Deep Interview Transcript Summary: TIPA US Academic Collaborator Agent

Profile: standard
Context type: greenfield
Final ambiguity: ~8%
Threshold: <=20%
Context snapshot: `.omx/context/tipa-us-researcher-commercialization-agent-20260521T191556Z.md`
Research artifact: `.omx/context/tipa-feature-difficulty-research-20260521T193655Z.md`

## Rounds

1. Q: For the 2-hour demo, what should “who should they actually call?” primarily mean?
   A: US academic research collaborators.

2. Q: What should be explicitly out of scope?
   A: Patent/IP analysis, non-academic industry contacts, and grant/funding matching are out of scope. The demo should focus on matching academic collaborators from supplied researcher identity. Python server acceptable; README run instructions required.

3. Q: What scoring signals matter beyond topic similarity?
   A: Region tag/filter, similar citation score, coauthor bridge distance, and method similarity.

4. Q: Which features should be functional vs heuristic/placeholder?
   A: User requested feature-difficulty research before approval.

5. Q: What if name + Google Scholar link are hard-required?
   A: Google Scholar helps human identity confirmation but should not be the machine data source because no official API/scraping is brittle. Prefer name + Semantic Scholar/ORCID, with Scholar link optional.

6. Q: Should V1 require name + ORCID/Semantic Scholar author link, with Google Scholar optional?
   A: Yes. Google Scholar link should be optional input.

7. Q: Is a fixed 5 ranked matches enough?
   A: No fixed 5. Return a sorted list of collaborators, allow user-set filters such as max_neighbor, and hide low-relevance researchers.

8. Closure update:
   A: Add a Run button so users can manually input parameters and rerun from the UI, instead of editing config files and restarting.

## Pressure-pass findings

- The original “5 matches” deliverable was revised: output should be a sorted, filterable collaborator list, not exactly 5.
- The Google Scholar assumption was revised: Scholar link is optional identity context, not a required machine-readable source.
- Complex scoring features are accepted as heuristics where necessary, but the UI and README must label them clearly.
