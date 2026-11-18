"""Pyomo LP: sets, parameters, variables, constraints V1-V9 and objectives F1, F2.

Time convention: slot t = 1..24 covers the clock interval [t-1, t); shifts 06-22 are the
slots 7..22; a pick in slot t > c (cut-off) is late by t - c hours.

- ``inputs.build(reg, days)`` turns the registry and the representative days into arrays;
- ``lp.build_model(inputs)`` builds the LP;
- ``solve.solve`` / ``solve.lexicographic`` optimise F1 or F2.
"""
