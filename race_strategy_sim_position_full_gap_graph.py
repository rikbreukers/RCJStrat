
import streamlit as st
import numpy as np
import pandas as pd
import plotly.graph_objects as go

st.set_page_config(page_title="Race Strategy Simulator", layout="wide")
st.title("🏁 Position-Aware Race Strategy Simulator")

# Sidebar inputs
st.sidebar.header("Simulation Inputs")
max_fuel = st.sidebar.number_input("Max Fuel Tank Size (L)", value=110)
fuel_usage_green = st.sidebar.number_input("Fuel Usage per Lap (Green) (L)", value=3.2)
fuel_usage_code60 = st.sidebar.number_input("Fuel Usage per Lap (Code 60) (L)", value=1.4)
pit_speed = st.sidebar.number_input("Pit Lane Speed Limit (kph)", value=40)
avg_lap_time = st.sidebar.number_input("Average Green Lap Time (s)", value=145)
circuit_length = st.sidebar.number_input("Circuit Length (km)", value=7.004)
pitlane_length = st.sidebar.number_input("Pit Lane Length (km)", value=1.0)
refuel_rate = st.sidebar.number_input("Refuel Flow Rate (s per liter)", value=1.875)
pit_overhead = st.sidebar.number_input("Pitstop Overhead (fixed sec)", value=10)

num_code60 = st.sidebar.slider("Number of Code 60s", 0, 30, 14)
code60_min = st.sidebar.number_input("Min Code 60 Duration (min)", value=5.0)
code60_max = st.sidebar.number_input("Max Code 60 Duration (min)", value=20.0)

sim_count = st.sidebar.number_input("Number of Simulations", min_value=1, max_value=1000, value=100)
simulate = st.sidebar.button("Run Simulations")

if "results" not in st.session_state:
    st.session_state.results = None
    st.session_state.logs = None
    st.session_state.times = None
    st.session_state.gaps = None

if simulate:
    results = []
    detailed_logs = []
    final_times = []
    gap_totals = []

    for sim in range(sim_count):
        code60_laps = np.sort(np.random.choice(range(10, 270), num_code60, replace=False))
        code60_durations = [
            int((np.random.uniform(8, 13) if np.random.rand() < 0.8 else np.random.uniform(code60_min, code60_max)) * 60)
            for _ in range(num_code60)
        ]
        code60_map = dict(zip(code60_laps, code60_durations))

        def run_strategy(strategy):
            fuel = max_fuel
            total_seconds = 0
            laps = 0
            trace = []
            last_green_pit_lap = -10
            code60_used = set()
            lap_time_log = []

            while total_seconds < 43200:
                laps += 1
                is_code60 = laps in code60_map
                lap_time = code60_map[laps] if is_code60 else avg_lap_time
                fuel_burn = fuel_usage_code60 if is_code60 else fuel_usage_green
                fuel -= fuel_burn
                lap_event = "CODE 60" if is_code60 else "GREEN"
                refueled = None
                pit_duration = None

                if fuel < fuel_usage_green:
                    remaining = (43200 - total_seconds) // avg_lap_time
                    needed = remaining * fuel_usage_green
                    refuel_amt = min(max_fuel if strategy == "full" else 90, needed)
                    fuel_time = refuel_amt * refuel_rate + pit_overhead
                    pit_travel_time = (pitlane_length / pit_speed) * 3600 - 9
                    total_seconds += fuel_time + pit_travel_time
                    fuel += refuel_amt
                    refueled = refuel_amt
                    pit_duration = round(fuel_time + pit_travel_time, 1)
                    last_green_pit_lap = laps

                if is_code60 and laps not in code60_used:
                    since_pit = laps - last_green_pit_lap
                    burned = since_pit * fuel_usage_green
                    space = max_fuel - fuel
                    can_refuel = (
                        (strategy == "partial" and space >= 15) or
                        (strategy == "full" and burned >= 15 and space >= 15)
                    )
                    if can_refuel:
                        time_into_lap = avg_lap_time * 0.5
                        km_into_lap = (time_into_lap / avg_lap_time) * circuit_length
                        km_to_pit_entry = circuit_length - km_into_lap
                        time_to_pit_entry = km_to_pit_entry / 60 * 3600
                        refuel_amt = min(28, space)
                        fuel_time = refuel_amt * refuel_rate + pit_overhead
                        pit_travel_time = (pitlane_length / pit_speed) * 3600 - 9
                        total_pit_time = fuel_time + pit_travel_time
                        time_needed = time_to_pit_entry + total_pit_time

                        if time_needed < code60_map[laps]:
                            fuel += refuel_amt
                            total_seconds += total_pit_time
                            refueled = refuel_amt
                            pit_duration = round(total_pit_time, 1)
                            code60_used.add(laps)

                trace.append({
                    "Lap": laps,
                    "Type": lap_event,
                    "Fuel": round(fuel, 1),
                    "Time (s)": int(total_seconds),
                    "Pit": refueled,
                    "Pit Duration": pit_duration
                })
                lap_time_log.append(int(total_seconds))
                total_seconds += lap_time

            return laps, total_seconds, trace, lap_time_log

        laps_full, time_full, trace_full, lap_times_full = run_strategy("full")
        laps_partial, time_partial, trace_partial, lap_times_partial = run_strategy("partial")

        if laps_full > laps_partial:
            winner = "Full"
            gap = (laps_full - laps_partial - 1) * avg_lap_time + avg_lap_time * 0.5
        elif laps_partial > laps_full:
            winner = "Partial"
            gap = (laps_partial - laps_full - 1) * avg_lap_time + avg_lap_time * 0.5
        else:
            if time_full < time_partial:
                winner = "Full (by time)"
                gap = abs(time_full - time_partial)
            elif time_partial < time_full:
                winner = "Partial (by time)"
                gap = abs(time_partial - time_full)
            else:
                winner = "Tie"
                gap = 0

        results.append({
            "Sim": sim + 1,
            "Full Laps": laps_full,
            "Partial Laps": laps_partial,
            "Winner": winner
        })
        detailed_logs.append({
            "Sim": sim + 1,
            "Full": trace_full,
            "Partial": trace_partial,
            "LapTimesFull": lap_times_full,
            "LapTimesPartial": lap_times_partial
        })
        final_times.append((sim + 1, laps_full, time_full, laps_partial, time_partial))
        gap_totals.append(gap)

    st.session_state.results = pd.DataFrame(results)
    st.session_state.logs = detailed_logs
    st.session_state.times = final_times
    st.session_state.gaps = gap_totals

if st.session_state.results is not None:
    df_results = st.session_state.results
    logs = st.session_state.logs
    times = st.session_state.times
    gaps = st.session_state.gaps

    st.markdown("### 🏁 Results Summary")
    summary = df_results["Winner"].value_counts()
    full_wins = summary.get("Full", 0) + summary.get("Full (by time)", 0)
    total = len(df_results)
    win_percent = (full_wins / total) * 100
    avg_gap = np.mean(gaps)
    st.write(f"✅ Full Strategy Wins: {full_wins} out of {total} simulations ({win_percent:.1f}%)")
    st.write(f"🔢 Average time gap between strategies: {avg_gap:.1f} seconds")
    st.dataframe(df_results, use_container_width=True)

    sim_id = st.selectbox("🔍 Select a Simulation to Visualize", df_results["Sim"])
    sim_data = next((log for log in logs if log["Sim"] == sim_id), None)

    if sim_data:
        st.markdown("### 📊 Lap-by-Lap Race Timeline")
        fig = go.Figure()
        for strat in ["Full", "Partial"]:
            y_val = 1 if strat == "Full" else 0
            for lap in sim_data[strat]:
                color = "purple" if lap["Type"] == "CODE 60" else "green"
                fig.add_trace(go.Scatter(
                    x=[lap["Lap"]],
                    y=[y_val],
                    mode="markers",
                    marker=dict(color=color, size=10),
                    hovertemplate=f"{strat} - Lap {lap['Lap']}<br>{lap['Type']}<br>Fuel: {lap['Fuel']}L<br>" +
                                  (f"⛽ Pit: {lap['Pit']}L<br>Duration: {lap['Pit Duration']}s" if lap["Pit"] else "")
                ))

        fig.update_layout(
            title="Race Timeline Visualization",
            yaxis=dict(tickvals=[1, 0], ticktext=["Full Strategy", "Partial Strategy"]),
            xaxis_title="Lap",
            height=400,
            showlegend=False
        )
        st.plotly_chart(fig, use_container_width=True)

        st.markdown("### ⏱️ Gap Evolution (seconds)")
        full_times = sim_data["LapTimesFull"]
        partial_times = sim_data["LapTimesPartial"]
        min_len = min(len(full_times), len(partial_times))
        gaps_per_lap = [partial_times[i] - full_times[i] for i in range(min_len)]
        st.line_chart(pd.DataFrame({"Gap (s)": gaps_per_lap}))
