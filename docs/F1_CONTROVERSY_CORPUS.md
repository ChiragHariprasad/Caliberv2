# CALIBRE — Historical F1 Controversy Corpus (2021–2026)

**Document Type:** Formal Research Corpus & Empirical Verification Dataset  
**Scope:** 10 Most Significant Controversial Formula 1 Grand Prix Races from 1 January 2021 Onwards  
**Mandatory Baseline:** Abu Dhabi 2021  
**Methodological Invariant:** Distinguish documented facts from disputed interpretations. CALIBRE evaluates evidence adequacy, provenance, and consistency—it never manufactures faults where none existed, nor does it issue sporting penalties.

---

## 1. Corpus Selection & Ranking Methodology

The 10 races selected represent the most consequential disputes in modern Formula 1 regarding:
1. **Safety Car & Session Neutralisation Procedures:** Ambiguity in regulation wording, partial unlapping, and restart timing.
2. **Track Limits & Transponder vs Video Corroboration:** Processing overload, delayed enforcement, and sensor uncertainty.
3. **Vehicle Telemetry & Deceleration Adjudication:** Brake pressure, throttle position, and kinematic plausibility in collision disputes.
4. **Spatial Geometry & Reference Line Crossings:** Pit exit/entry line boundaries, transponder gate positions, and GPS trajectory interpolation.
5. **Weather & Extreme Session State Management:** Premature classifications, red flag countback rules, and session-clock expiration.
6. **Track Safety & Hazard Verification:** Recovery vehicles on live circuits, loose track infrastructure, and flag status propagation.

---

## 2. Ranked List of the 10 Controversial Races

```text
+------+-----------------------------+-----------------------+-------------+------------------------------------------------------+
| Rank | Grand Prix                  | Circuit & Country     | Date        | Primary Controversy Dimension                         |
+------+-----------------------------+-----------------------+-------------+------------------------------------------------------+
|  01  | Abu Dhabi Grand Prix        | Yas Marina, UAE       | 12 Dec 2021 | Safety Car unlapping & restart timing (Art 48.12)    |
|  02  | Belgian Grand Prix          | Spa-Francorchamps, BE | 29 Aug 2021 | 2-lap SC race in extreme rain & countback rule       |
|  03  | Saudi Arabian Grand Prix    | Jeddah Corniche, SA   | 05 Dec 2021 | Lap 37 brake-test telemetry & radio grid bargaining  |
|  04  | British Grand Prix          | Silverstone, UK       | 18 Jul 2021 | Copse 51G crash; GPS simulation petition for review  |
|  05  | Austrian Grand Prix         | Red Bull Ring, AT     | 02 Jul 2023 | 1,200+ track limit violations & post-finality penalty|
|  06  | Australian Grand Prix       | Albert Park, AU       | 02 Apr 2023 | 3 red flags, chaotic T1 restart & countback grid     |
|  07  | Japanese Grand Prix         | Suzuka, JP            | 09 Oct 2022 | Recovery crane on live track & full points confusion |
|  08  | Monaco Grand Prix           | Circuit de Monaco, MC | 29 May 2022 | Pit exit line crossing & starting light system failure|
|  09  | United States Grand Prix    | COTA, Austin, USA     | 20 Oct 2024 | Lap 52 Turn 12 apex ownership & driving guidelines   |
|  10  | Las Vegas Grand Prix        | Las Vegas Strip, USA  | 16 Nov 2023 | FP1 water valve cover failure & penalty discretion   |
+------+-----------------------------+-----------------------+-------------+------------------------------------------------------+
```

---

## 3. Comprehensive Race Dossiers

### Race 01: 2021 Abu Dhabi Grand Prix (Mandatory Baseline)
- **Event:** Formula 1 Etihad Airways Abu Dhabi Grand Prix 2021
- **Circuit / Country:** Yas Marina Circuit, Abu Dhabi, United Arab Emirates
- **Date:** 12 December 2021
- **Drivers / Teams Involved:** Lewis Hamilton (Mercedes-AMG Petronas F1 Team), Max Verstappen (Red Bull Racing), Michael Masi (FIA F1 Race Director).
- **Executive Summary:** Nicholas Latifi crashed at Turn 14 on Lap 53, triggering a full Safety Car. Hamilton led on worn hard tyres; Verstappen pitted for fresh soft tyres. On Lap 56, Race Control initially displayed "LAPPED CARS WILL NOT BE ALLOWED TO OVERTAKE". On Lap 57, Race Control reversed direction and sent message "LAPPED CARS 4 (NOR), 14 (ALO), 31 (OCO), 16 (LEC), 5 (VET) TO OVERTAKE SAFETY CAR"—allowing only the five cars between Hamilton and Verstappen to unlap, while leaving cars behind Verstappen (e.g. Ricciardo, Stroll) in place. Simultaneously, the Safety Car was called in at the end of Lap 57 rather than the end of the *following* lap. On Lap 58, Verstappen overtook Hamilton at Turn 5 to win the race and the 2021 Drivers' World Championship.
- **Key Disputed Decision / Incident:**
  1. The selective unlapping of five specific cars rather than "any cars that have been lapped" as specified in Article 48.12 of the 2021 FIA Formula One Sporting Regulations.
  2. Withdrawing the Safety Car on the same lap the unlap order was given, directly contradicting Article 48.12 ("once the last lapped car has passed the safety car the safety car will return to the pits at the end of the following lap").
  3. Race Director Masi's reliance on Article 15.3 (giving the Race Director "overriding authority" over the use of the safety car).
- **Documented Facts vs. Disputed Interpretations:**
  - *Documented Facts:*
    - Message 48 (16:32): "LAPPED CARS WILL NOT BE ALLOWED TO OVERTAKE".
    - Message 52 (16:36): "LAPPED CARS 4 - 14 - 31 - 16 - 5 TO OVERTAKE SAFETY CAR".
    - Message 54 (16:36): "SAFETY CAR IN THIS LAP".
    - Mercedes lodged protests under Articles 48.8 (overtaking under SC) and 48.12 (SC procedure). Both protests were dismissed by the Stewards (Doc 57 & Doc 58).
    - FIA World Motor Sport Council Report (19 March 2022) concluded: "The Race Director called the safety car back into the pit lane without it having completed an additional lap as required by the Formula 1 Sporting Regulations (Article 48.12)... The process of identifying lapped cars has up until now been a manual one and human error led to the fact that not all cars were allowed to un-lap themselves."
  - *Disputed Interpretations:*
    - Mercedes argued Article 48.12 is non-discretionary and mandatory; Red Bull argued Article 15.3 gave the Race Director absolute power to override Article 48.12 to ensure a green-flag finish.
- **Relevance to CALIBRE:**
  - **Contract C07 (Session-Status Integrity):** Evaluates whether session-state transitions (SAFETY_CAR $\rightarrow$ ENDING $\rightarrow$ GREEN) satisfy declared timing and regulatory preconditions.
  - **Absence & Monotonicity:** SIA's scheduled expectation pattern (P5) detects that an unlap instruction to a partial subset violates the contract rule-regime bindings (C13 / P8).
  - **Replay & Audit Trail:** CALIBRE preserves the exact sequence of race control messages, car order transponder timestamps, and track intervals in an immutable hash chain, demonstrating that the interval between Message 52 and Message 54 violated the minimum one-lap duration constraint.
- **Primary Source Documentation:**
  - FIA Stewards Decision Doc 57 (Protest against Car 33): [fia.com/documents](https://www.fia.com/documents)
  - FIA Stewards Decision Doc 58 (Protest by Mercedes against SC procedure): [fia.com/documents](https://www.fia.com/documents)
  - FIA World Motor Sport Council Inquiry Report on 2021 Abu Dhabi Grand Prix (19 March 2022).
  - 2021 FIA Formula One Sporting Regulations, Articles 15.3, 48.8, 48.12.

---

### Race 02: 2021 Belgian Grand Prix
- **Event:** Formula 1 Rolex Belgian Grand Prix 2021
- **Circuit / Country:** Circuit de Spa-Francorchamps, Stavelot, Belgium
- **Date:** 29 August 2021
- **Drivers / Teams Involved:** Max Verstappen (Red Bull), George Russell (Williams), Lewis Hamilton (Mercedes), Michael Masi (Race Director).
- **Executive Summary:** Relentless torrential rain caused multiple start aborts and a red flag before the race officially started. After a 3-hour weather delay, cars were sent onto the track behind the Safety Car for exactly 2 laps—the minimum necessary under Article 6.5 of the Sporting Regulations to constitute an official race and award half points. The race was then red-flagged and terminated. Classification was based on countback to the end of Lap 1.
- **Key Disputed Decision:** Running two laps behind the safety car purely to trigger the regulatory minimum for a commercial and sporting result, without any green-flag competition taking place.
- **Documented Facts vs. Disputed Interpretations:**
  - *Documented Facts:* Start delayed from 15:00. Two formation laps run; red flag at 15:25. Race resumed at 18:17 behind SC; red flag displayed on Lap 3 (18:27). Official classification taken after 1 lap. Half points awarded (Verstappen 12.5, Russell 9, Hamilton 7.5).
  - *Disputed Interpretations:* Several drivers (e.g. Hamilton, Alonso) argued "it wasn't a race" and was staged purely to satisfy commercial contracts. FIA stated it acted in the interest of safety while attempting to hold the event within the allowable time window.
- **Relevance to CALIBRE:**
  - **Contract C09 & C10 (Weather Reporting & Scope Locality):** Evaluates track standing water and visibility evidence. Demonstrates scope locality: weather outages affect track status decisions without invalidating prior dry timing references.
  - **Contract C07 (Session-Status Integrity):** Detects whether countback rules and minimum distance criteria are mathematically met before finality is sealed.
- **Primary Source Documentation:**
  - FIA Stewards Documents 18 through 23 (Doc 23: Official Final Classification).
  - 2021 FIA Formula One Sporting Regulations, Articles 6.5, 50, 51.

---

### Race 03: 2021 Saudi Arabian Grand Prix
- **Event:** Formula 1 STC Saudi Arabian Grand Prix 2021
- **Circuit / Country:** Jeddah Corniche Circuit, Jeddah, Saudi Arabia
- **Date:** 05 December 2021
- **Drivers / Teams Involved:** Max Verstappen (Red Bull), Lewis Hamilton (Mercedes).
- **Executive Summary:** A chaotic inaugural race featuring two red flags, multiple virtual safety cars, and unprecedented radio negotiations where Race Director Masi offered Red Bull grid positions for the restart. On Lap 37, Verstappen was instructed to cede position to Hamilton after running off track at Turn 1. Verstappen slowed down on the back straight between Turns 26 and 27; Hamilton, unaware that Verstappen was giving the position back, ran into the back of Verstappen's car, damaging Hamilton's front wing.
- **Key Disputed Decision:** Whether Verstappen deliberately "brake-tested" Hamilton or whether Hamilton failed to overtake an intentionally slowing car.
- **Documented Facts vs. Disputed Interpretations:**
  - *Documented Facts:* Stewards investigated post-race and examined car telemetry (Doc 43). Telemetry proved Verstappen braked with 69 bar of pressure, causing 2.4g of sudden deceleration while Hamilton was directly behind him. Verstappen was penalised 10 seconds post-race.
  - *Disputed Interpretations:* Red Bull argued Verstappen was strategically allowing Hamilton past before the DRS detection line; Mercedes argued the sudden 69-bar braking was erratic and dangerous.
- **Relevance to CALIBRE:**
  - **Contract C04 (Vehicle Kinematic Plausibility):** Deceleration exceeding 2.4g on a straight without an obstacle or yellow flag triggers an immediate `KINEMATIC_ANOMALY` witness.
  - **Contract C05 (Telemetry Time Alignment):** Cross-aligns car ECU telemetry (brake pressure, wheel speed) against FIA transponder loop time to verify whether the deceleration coincided with driver approach.
- **Primary Source Documentation:**
  - FIA Stewards Decision Doc 43 (Car 33 - Causing a collision): [fia.com/documents](https://www.fia.com/documents)
  - FIA Stewards Decision Doc 34 & 35 (Restart grid determinations).

---

### Race 04: 2021 British Grand Prix
- **Event:** Formula 1 Pirelli British Grand Prix 2021
- **Circuit / Country:** Silverstone Circuit, Towcester, United Kingdom
- **Date:** 18 July 2021
- **Drivers / Teams Involved:** Lewis Hamilton (Mercedes), Max Verstappen (Red Bull).
- **Executive Summary:** On Lap 1, Hamilton and Verstappen engaged in a fierce wheel-to-wheel duel culminating in a high-speed collision at the 290 km/h Copse corner. Verstappen suffered a 51G lateral impact with the tyre barrier, destroying his car and requiring hospital checks. The race was red-flagged. Stewards penalised Hamilton 10 seconds for being "predominantly to blame" (Doc 34). Hamilton served the penalty at his pit stop and recovered to win. Red Bull subsequently petitioned for a Right of Review under Article 14 of the International Sporting Code, submitting GPS trajectory simulations and telemetry comparisons with other drivers.
- **Key Disputed Decision:** Stewards' 10-second penalty decision, followed by the dismissal of Red Bull's petition for review (Doc 49).
- **Documented Facts vs. Disputed Interpretations:**
  - *Documented Facts:* Red Bull created GPS trajectory simulations recreating Hamilton's line compared to his qualifying lap and his later pass on Norris. Stewards ruled that team-created simulations do not constitute "new evidence discovered" under the ISC, dismissing the petition.
  - *Disputed Interpretations:* Red Bull argued Hamilton could not have made Copse corner without running wide; Mercedes argued Hamilton held the inside line and was entitled to racing room.
- **Relevance to CALIBRE:**
  - **Contract C06 (Position & Track Consistency):** Evaluates GPS coordinate trajectories against track boundaries.
  - **Evidence Provenance & Lineage:** Distinguishes verified raw GPS position telemetry from derived synthetic simulations, illustrating SIA's rule that derived models cannot masquerade as independent measurement origins.
- **Primary Source Documentation:**
  - FIA Stewards Decision Doc 34 (Car 44 collision with Car 33).
  - FIA Stewards Decision Doc 49 (Red Bull Racing Petition for Right of Review).
  - FIA International Sporting Code, Article 14.

---

### Race 05: 2023 Austrian Grand Prix
- **Event:** Formula 1 Grosser Preis von Österreich 2023
- **Circuit / Country:** Red Bull Ring, Spielberg, Austria
- **Date:** 02 July 2023
- **Drivers / Teams Involved:** Entire grid, Aston Martin Aramco F1 Team, FIA Race Control.
- **Executive Summary:** The Red Bull Ring's Turns 9 and 10 saw an unprecedented deluge of track limits violations. Race Control was inundated with over 1,200 potential reports from loop sensors and video cameras and could not review them in real time during the 71-lap race. Following the race, Aston Martin lodged a formal protest against the provisional classification (Doc 71), claiming numerous track limits infringements had not been penalised. The Stewards upheld the protest, reviewed over 1,200 video and sensor captures over five hours post-race, and applied 12 separate time penalties to 8 drivers, fundamentally altering the final classification.
- **Key Disputed Decision:** Complete overload of the evidence review pipeline during live competition, resulting in post-finality retro-penalties five hours after the podium ceremony.
- **Documented Facts vs. Disputed Interpretations:**
  - *Documented Facts:* FIA Stewards Doc 71 (Aston Martin protest upheld) noted: "Having considered the request from the Competitor, the Stewards find that the Competitor has submitted relevant and significant evidence... Race Control had to review over 1200 instances where a car was reported as potentially leaving the track." Post-race penalties: Sainz (+10s), Hamilton (+10s), Gasly (+10s), Albon (+10s), Ocon (+30s total across 4 penalties), Sargeant (+10s), De Vries (+15s), Tsunoda (+5s).
- **Relevance to CALIBRE:**
  - **Contract C06 (Position and Track Consistency):** Directly addresses the failure of timing loop sensors alone to resolve track limit exceedances without video corroboration.
  - **Bitemporal Ledger & Post-Finality Amendments:** Demonstrates CALIBRE's core principle that late evidence arriving after finality produces counterfactual **Amendment Notices** rather than silently rewriting past historical beliefs.
- **Primary Source Documentation:**
  - FIA Stewards Decision Doc 71 (Aston Martin Protest): [fia.com/documents](https://www.fia.com/documents)
  - FIA Stewards Decision Doc 73 (Post-Race Penalties and Amended Classification).

---

### Race 06: 2023 Australian Grand Prix
- **Event:** Formula 1 Rolex Australian Grand Prix 2023
- **Circuit / Country:** Albert Park Circuit, Melbourne, Australia
- **Date:** 02 April 2023
- **Drivers / Teams Involved:** Carlos Sainz (Ferrari), Fernando Alonso (Aston Martin), Alpine (Gasly/Ocon), FIA Race Control.
- **Executive Summary:** The race was halted by three separate red flags. The third red flag occurred following a chaotic standing restart on Lap 56 of 58: Sainz spun Alonso at Turn 1, the two Alpines collided into the wall, Sargeant rear-ended De Vries, and Stroll went into the gravel. The session was red-flagged before cars completed Sector 1. A 30-minute delay ensued while Race Control debated whether the race was finished and what the order should be. Under Article 57.3, Race Control determined the restart order should be taken from the previous restart grid minus the cars unable to continue. The race concluded with a single procession lap behind the Safety Car. Sainz was handed a 5-second penalty for spinning Alonso, dropping him from 4th to 12th (last of running cars).
- **Key Disputed Decision:** Deciding the restart classification based on the previous grid (which saved Alonso's podium) while simultaneously penalising Sainz for an incident that occurred during a restart lap that was effectively voided. Ferrari's Petition for Review was subsequently rejected (Doc 52).
- **Documented Facts vs. Disputed Interpretations:**
  - *Documented Facts:* Ferrari submitted telemetry showing Sainz braked in dirty air with cold tyres and driver testimony. Stewards dismissed the petition, ruling the data was not "significant and relevant" new evidence.
- **Relevance to CALIBRE:**
  - **CR-1 (Decision Voiding):** Demonstrates why legitimate absence or lap annulment must cleanly void decision instances with a `VOIDED` witness rather than leaving slots open or yielding false `DEGRADED` states.
  - **Contract C07 (Session-Status Integrity):** Audits state transitions across multiple red-flag restarts and countback boundaries.
- **Primary Source Documentation:**
  - FIA Stewards Decision Doc 45 (Car 55 penalty).
  - FIA Stewards Decision Doc 52 (Ferrari Right of Review Dismissal).
  - 2023 FIA Formula One Sporting Regulations, Articles 57.3, 58.

---

### Race 07: 2022 Japanese Grand Prix
- **Event:** Formula 1 Honda Japanese Grand Prix 2022
- **Circuit / Country:** Suzuka International Racing Course, Suzuka, Japan
- **Date:** 09 October 2022
- **Drivers / Teams Involved:** Pierre Gasly (AlphaTauri), Max Verstappen (Red Bull), Charles Leclerc (Ferrari), Eduardo Freitas (Race Director).
- **Executive Summary:** Running in extreme rain, Carlos Sainz crashed on Lap 1. The Safety Car was deployed, followed immediately by a red flag. Pierre Gasly, who had pitted to remove a sponsor signboard stuck to his front wing, was driving at high speed to catch the safety car queue in near-zero visibility when he encountered a mobile recovery vehicle (crane/tractor) on the live track. Gasly expressed intense fury over team radio given the fatal 2014 Suzuka crash of Jules Bianchi under similar circumstances. Gasly was subsequently penalised 20 seconds post-race for speeding under red flags (up to 251 km/h). When the race restarted after a 2-hour delay, it ran to the 3-hour window limit (completing 28 of 53 laps). Due to a drafting quirk in Article 6.5 (which reduced points only if a race "cannot be resumed"), full championship points were awarded because the race finished under green, making Verstappen World Champion on the spot.
- **Key Disputed Decision:** Deploying heavy recovery machinery onto a live track before all cars were secured behind the safety car; confusion regarding points allocation under shortened race distance.
- **Documented Facts vs. Disputed Interpretations:**
  - *Documented Facts:* FIA launched an immediate procedural review (published 21 October 2022), concluding: recovery vehicles should not be deployed until all cars are grouped; dynamic VSC-style speed delta enforced in red flags; Article 6.5 points table reworded for 2023. Gasly penalised via Doc 36 for speeding.
- **Relevance to CALIBRE:**
  - **Contract C08 (Incident Timing & Hazard Exposure):** Cross-checks recovery vehicle deployment timestamps against car GPS positions and red flag broadcast times.
  - **Contract C13 (Rule-Regime Consistency):** Verifies that the points allocation formula matches the exact textual rule regime in force for the season.
- **Primary Source Documentation:**
  - FIA Report into Suzuka 2022 Incident (21 October 2022).
  - FIA Stewards Decision Doc 36 (Car 10 - Speeding under Red Flag).
  - 2022 FIA Formula One Sporting Regulations, Article 6.5.

---

### Race 08: 2022 Monaco Grand Prix
- **Event:** Formula 1 Grand Prix de Monaco 2022
- **Circuit / Country:** Circuit de Monaco, Monte Carlo, Monaco
- **Date:** 29 May 2022
- **Drivers / Teams Involved:** Sergio Perez (Red Bull), Max Verstappen (Red Bull), Scuderia Ferrari.
- **Executive Summary:** Delayed by a heavy downpour and a power cut that disabled starting lights and race control systems. During the transition from wet to dry tyres, Red Bull cars emerged from the pits ahead of Ferrari. Ferrari formally protested Perez (Doc 56) and Verstappen (Doc 57) for allegedly crossing the yellow pit exit line when blending back onto the track. Stewards dismissed both protests, ruling that according to the 2022 FIA International Sporting Code (Appendix L, Chapter IV, Article 4c), a car must have a full tyre entirely across the line to be in breach, whereas the previous interpretation prohibited touching the line.
- **Key Disputed Decision:** Rule interpretation of "touching" vs "crossing" the pit exit boundary line, and power failure affecting official timing systems.
- **Documented Facts vs. Disputed Interpretations:**
  - *Documented Facts:* Video and high-resolution stills showed Verstappen's left front tyre rode on top of the yellow line without being fully to the left of it. Stewards noted the wording in the ISC had been updated from "must not cross" to "must not cut across" and required a wheel to be completely over.
- **Relevance to CALIBRE:**
  - **Contract C06 & C13 (Spatial Integrity & Rule-Regime Binding):** Direct demonstration of Pattern P2 (effective-dated reference). A geometric constraint that checked "wheel touching yellow line" was valid for the 2021 season but expired and invalid for 2022 under amended ISC Appendix L.
- **Primary Source Documentation:**
  - FIA Stewards Decision Doc 56 (Protest against Car 11).
  - FIA Stewards Decision Doc 57 (Protest against Car 1).
  - 2022 FIA International Sporting Code, Appendix L, Chapter IV, Article 4c.

---

### Race 09: 2024 United States Grand Prix
- **Event:** Formula 1 Pirelli United States Grand Prix 2024
- **Circuit / Country:** Circuit of the Americas, Austin, Texas, USA
- **Date:** 20 October 2024
- **Drivers / Teams Involved:** Lando Norris (McLaren), Max Verstappen (Red Bull).
- **Executive Summary:** On Lap 52, Norris attacked Verstappen on the outside into Turn 12. Both cars braked extremely late and ran wide off the track surface. Norris completed the pass entirely off-track on the tarmac run-off area and did not give the position back. Stewards awarded Norris a 5-second time penalty (Doc 69) for "leaving the track and gaining a lasting advantage". This dropped Norris from 3rd to 4th, promoting Verstappen to the podium and expanding his championship lead. McLaren submitted a Petition for Right of Review (Doc 78), arguing that Verstappen had released his brakes to reach the apex first and had driven Norris off track.
- **Key Disputed Decision:** Application of the FIA Driving Standards Guidelines regarding "ownership of the corner at the apex", where telemetry indicated the defending driver only reached the apex first because he did not attempt to make the corner within track limits.
- **Documented Facts vs. Disputed Interpretations:**
  - *Documented Facts:* Stewards Doc 69 found Car 4 was not level at the apex and therefore had lost the right to the corner; McLaren's Right of Review was dismissed (Doc 78) because the allegation of error in the stewards' assessment does not constitute new evidence under Art 14.
- **Relevance to CALIBRE:**
  - **Contract C04 & C06 (Vehicle Kinematics & Spatial Apex Tracking):** Combines steering angle, deceleration g-force, and spatial apex proximity to evaluate whether an overtaking trajectory was physically capable of staying within track boundaries.
- **Primary Source Documentation:**
  - FIA Stewards Decision Doc 69 (Car 4 - Leaving track and gaining lasting advantage).
  - FIA Stewards Decision Doc 78 (McLaren Right of Review Dismissal).
  - FIA Driving Standards Guidelines 2024.

---

### Race 10: 2023 Las Vegas Grand Prix
- **Event:** Formula 1 Heineken Silver Las Vegas Grand Prix 2023
- **Circuit / Country:** Las Vegas Strip Circuit, Las Vegas, Nevada, USA
- **Date:** 16 November 2023
- **Drivers / Teams Involved:** Carlos Sainz (Ferrari), Ferrari, FIA Stewards.
- **Executive Summary:** Just eight minutes into Free Practice 1 on the newly constructed Las Vegas Strip street circuit, Carlos Sainz's Ferrari struck an unsecured concrete water valve cover frame at over 320 km/h on the long Strip straight. The violent impact tore a hole through the floor, destroyed the battery pack (Energy Store), internal combustion engine, and monocoque survival cell, causing an immediate red flag and cancelling the remainder of FP1. Ferrari was forced to replace the power unit components, exceeding the season allocation. Ferrari requested a sporting force majeure exemption. Stewards issued Document 17, stating they had spent hours attempting to find a regulatory mechanism to waive the 10-place grid penalty, but concluded that Article 28.2 of the Sporting Regulations gave them zero discretion to do so regardless of external circumstances.
- **Key Disputed Decision:** Enforcing a sporting grid penalty on a competitor whose car was destroyed by a failure of the FIA/circuit promoter's own track safety infrastructure.
- **Documented Facts vs. Disputed Interpretations:**
  - *Documented Facts:* Stewards Doc 17 explicitly states: "The Stewards note that if they had the authority to grant a derogation in what they consider in this case to be mitigating, unusual and unfortunate circumstances, they would have done so, however the regulations do not allow such action to be taken."
- **Relevance to CALIBRE:**
  - **Contract C11 (Feed & Infrastructure Guard Integrity):** Represents an external track-hardware failure where guard facts (circuit infrastructure readiness) were invalid.
  - **Contract C13 (Rule-Regime Inflexibility):** Demonstrates parameter and constraint rigidity where sporting regulations lack an exception branch.
- **Primary Source Documentation:**
  - FIA Stewards Decision Doc 17 (Car 55 - Replacement of Survival Cell and PU components).
  - 2023 FIA Formula One Sporting Regulations, Article 28.2.

---

## 4. Empirical Summary: Why These 10 Races Validate CALIBRE

| Race | Relevant Contracts | Key Evidence Problem Investigated |
|---|---|---|
| **2021 Abu Dhabi** | C07, C13, C01 | Neutralisation state transition before mandatory unlap cycle completes. |
| **2021 Belgium** | C07, C09, C10 | Minimum session elapsed duration vs countback classification rules in rain. |
| **2021 Saudi Arabia** | C04, C05, C08 | 2.4g / 69-bar sudden deceleration on straight; kinematic anomaly witness. |
| **2021 Great Britain** | C04, C06 | Raw telemetry vs simulated derived models; two-axis origin closure. |
| **2023 Austria** | C06, C11, C12 | Transponder vs video corroboration failure; post-finality amendments. |
| **2023 Australia** | C01, C07, C08 | Red flag countback ordering and decision voiding on restarted laps. |
| **2022 Japan** | C08, C11, C13 | Live recovery vehicle hazard presence vs red flag speed compliance. |
| **2022 Monaco** | C06, C13 | Effective-dated reference expiration (ISC line crossing rule update). |
| **2024 United States** | C04, C06 | Trajectory kinematics and apex proximity under driving guidelines. |
| **2023 Las Vegas** | C11, C13 | Track infrastructure guard failure; rule-regime limit enforcement. |

