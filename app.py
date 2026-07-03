import streamlit as st
import os
import time
import json
import pandas as pd
from datetime import datetime
from parser import parse_runbook
from executor import execute_step, force_execute_step, RISKY_STEPS
from report import generate_report
from auth import authenticate_user, initialize_users
from permissions import (
    can_execute_runbook,
    can_approve_risky_action,
    can_view_audit_logs,
    can_view_active_users,
    save_active_run,
    load_active_run,
    delete_active_run,
    get_pending_runs
)
from audit import write_audit_log, read_audit_logs
from active_users import track_user_activity, remove_active_user, get_active_users
from failure_analysis import analyze_failure, get_failures
from data_stores import load_audit_annotations, update_audit_comment

# Initialize users database if not exists
initialize_users()

# ----------------------------------------------------
# PAGE CONFIGURATION
# ----------------------------------------------------
st.set_page_config(
    page_title="Runbook Following Agent",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ----------------------------------------------------
# CUSTOM AESTHETICS & STYLING
# ----------------------------------------------------
st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;700&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Outfit', sans-serif;
    }
    
    .main-title {
        font-size: 2.8rem;
        font-weight: 700;
        background: linear-gradient(90deg, #1f77b4, #00d2ff);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0.2rem;
    }
    
    .subtitle {
        font-size: 1.2rem;
        color: #888888;
        margin-bottom: 2rem;
    }
    </style>
    """,
    unsafe_allow_html=True
)

# ----------------------------------------------------
# INITIALIZE SESSION STATES
# ----------------------------------------------------
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.username = ""
    st.session_state.role = ""
    st.session_state.runbook_source = None
    st.session_state.runbook_content = None
    st.session_state.uploaded_file_name = None
    st.session_state.last_uploaded_name = None
    st.session_state.last_uploaded_content = None
    st.session_state.run_state = "IDLE"  # IDLE, RUNNING, COMPLETED
    st.session_state.results = []
    st.session_state.waiting_for_approval = False
    st.session_state.report_path = None
    st.session_state.run_id = None
    st.session_state.timeline = []
    st.session_state.failures = []
    st.session_state.recommendations = []
    st.session_state.last_login = ""
    st.session_state.last_activity = 0.0

base_dir = os.path.dirname(os.path.abspath(__file__))

# Session timeout check (30 minutes)
TIMEOUT_SECONDS = 1800
if st.session_state.logged_in:
    if st.session_state.last_activity > 0.0:
        elapsed = time.time() - st.session_state.last_activity
        if elapsed > TIMEOUT_SECONDS:
            remove_active_user(st.session_state.username)
            write_audit_log(st.session_state.username, st.session_state.role, "TIMEOUT_LOGOUT", details="Session timed out due to inactivity.")
            st.session_state.logged_in = False
            st.session_state.username = ""
            st.session_state.role = ""
            st.session_state.waiting_for_approval = False
            st.warning("⏱️ Session expired due to inactivity. Please sign in again.")
            st.rerun()
        elif TIMEOUT_SECONDS - elapsed <= 300:
            st.sidebar.warning(f"⚠️ Session expires in {int((TIMEOUT_SECONDS - elapsed) // 60)} minutes.")
            if st.sidebar.button("Extend Session"):
                st.session_state.last_activity = time.time()
                st.rerun()

# ----------------------------------------------------
# 1. AUTHENTICATION & LOGIN PAGE
# ----------------------------------------------------
if not st.session_state.logged_in:
    # Centered glassmorphic login card CSS
    st.markdown(
        """
        <style>
        [data-testid="stSidebar"] {
            display: none !important;
        }
        [data-testid="stHeader"] {
            display: none !important;
        }
        .main .block-container {
            max-width: 440px !important;
            padding-top: 5rem !important;
            padding-bottom: 5rem !important;
            margin: auto !important;
        }
        .login-logo {
            font-size: 3rem;
            margin-bottom: 1rem;
            display: inline-block;
        }
        .forgot-link {
            text-align: center;
            display: block;
            margin-top: 1rem;
            color: #64748b;
            font-size: 0.85rem;
            text-decoration: none;
        }
        .forgot-link:hover {
            color: #8b5cf6;
        }
        </style>
        """,
        unsafe_allow_html=True
    )
    
    st.markdown(
        """
        <div style="text-align: center; padding: 1.5rem 0;">
            <div class="login-logo">🤖</div>
            <h2 style="font-weight: 700; margin-bottom: 0.2rem; background: linear-gradient(90deg, #1f77b4, #00d2ff); -webkit-background-clip: text; -webkit-text-fill-color: transparent;">Runbook Agent</h2>
            <p style="color: #64748b; font-size: 0.95rem; margin-bottom: 2rem;">Secure incident response console access</p>
        </div>
        """,
        unsafe_allow_html=True
    )

    with st.form("login_form"):
        st.markdown("<h4 style='margin-bottom: 1.5rem; text-align: center;'>🔐 Sign In to Console</h4>", unsafe_allow_html=True)
        username = st.text_input("Username", placeholder="e.g. developer").strip()
        password = st.text_input("Password", type="password", placeholder="••••••••").strip()
        submitted = st.form_submit_button("Sign In", use_container_width=True)
        
        if submitted:
            user_info = authenticate_user(username, password)
            if user_info:
                st.session_state.logged_in = True
                st.session_state.username = user_info["username"]
                st.session_state.role = user_info["role"]
                st.session_state.last_login = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                st.session_state.last_activity = time.time()
                
                # Track session activity
                track_user_activity(user_info["username"], user_info["role"])
                write_audit_log(user_info["username"], user_info["role"], "LOGIN", details="Successful user login.")
                
                st.success("Authentication successful! Loading dashboard...")
                st.rerun()
            else:
                # Log failed / denied access attempt
                write_audit_log(
                    username if username else "anonymous",
                    "unknown",
                    "FAILED_LOGIN",
                    details=f"Denied access: failed login attempt for user '{username}'."
                )
                st.error("Invalid username or password. Access Denied.")
                
    st.stop()

# ----------------------------------------------------
# OPERATOR telemetry update on every page run
# ----------------------------------------------------
track_user_activity(st.session_state.username, st.session_state.role)

# ----------------------------------------------------
# SIDEBAR
# ----------------------------------------------------
st.sidebar.markdown("<h1 style='margin-bottom:0;'>🤖 Runbook Agent</h1>", unsafe_allow_html=True)
st.sidebar.caption("Production Incident Response Desk")
st.sidebar.markdown("---")

st.sidebar.markdown(f"<h4>👤 {st.session_state.username}</h4>", unsafe_allow_html=True)
role_color = "#10b981" if st.session_state.role == "manager" else "#8b5cf6"
st.sidebar.markdown(f"<span style='background-color: {role_color}; color: white; padding: 0.25rem 0.6rem; border-radius: 9999px; font-size: 0.8rem; font-weight: bold;'>{st.session_state.role.upper()}</span>", unsafe_allow_html=True)
st.sidebar.markdown(f"<div style='margin-top: 1rem; font-size: 0.85rem; color: #64748b;'>Last Login:<br><code>{st.session_state.last_login}</code></div>", unsafe_allow_html=True)
st.sidebar.markdown("<div style='margin-top: 0.5rem; font-size: 0.85rem; color: #10b981; font-weight: 600;'>🟢 Session Active</div>", unsafe_allow_html=True)

st.sidebar.markdown("---")
if st.sidebar.button("🔓 Sign Out", use_container_width=True):
    remove_active_user(st.session_state.username)
    write_audit_log(st.session_state.username, st.session_state.role, "LOGOUT", details="User signed out successfully.")
    
    # Clear local states
    st.session_state.logged_in = False
    st.session_state.username = ""
    st.session_state.role = ""
    st.session_state.runbook_source = None
    st.session_state.run_state = "IDLE"
    st.session_state.results = []
    st.session_state.waiting_for_approval = False
    st.session_state.report_path = None
    st.session_state.run_id = None
    st.session_state.timeline = []
    st.session_state.failures = []
    st.session_state.recommendations = []
    st.session_state.last_login = ""
    st.session_state.last_activity = 0.0
    st.rerun()

# ----------------------------------------------------
# RBAC NAVIGATION
# ----------------------------------------------------
st.sidebar.markdown("### 🗺️ Navigation")

pages = [
    "🏠 Dashboard Home",
    "📋 Runbooks",
    "🕵️ Audit Logs",
    "👥 Active Users",
    "📊 Reports",
    "📅 Incident Timeline",
    "🛠️ Failure Analysis"
]

selected_page = st.sidebar.radio("Go to Page", pages)

# ----------------------------------------------------
# HISTORICAL STATS LOADER
# ----------------------------------------------------
def load_historical_stats():
    reports_dir = os.path.join(base_dir, "reports")
    total_executions = 0
    successful_steps = 0
    failed_steps = 0
    skipped_steps = 0
    blocked_steps = 0
    reports_list = []
    
    if os.path.exists(reports_dir):
        files = [f for f in os.listdir(reports_dir) if f.endswith(".json")]
        total_executions = len(files)
        for f in files:
            try:
                with open(os.path.join(reports_dir, f), "r", encoding="utf-8") as rf:
                    data_dict = json.load(rf)
                    reports_list.append(data_dict)
                    summary = data_dict.get("summary", {})
                    successful_steps += summary.get("success", 0)
                    failed_steps += summary.get("failed", 0)
                    skipped_steps += summary.get("skipped", 0)
                    blocked_steps += summary.get("blocked", 0)
            except Exception:
                pass
    return {
        "total_executions": total_executions,
        "successful_steps": successful_steps,
        "failed_steps": failed_steps,
        "skipped_steps": skipped_steps,
        "blocked_steps": blocked_steps,
        "reports": reports_list
    }

# ----------------------------------------------------
# PAGE 1: 🏠 DASHBOARD HOME
# ----------------------------------------------------
if selected_page == "🏠 Dashboard Home":
    st.markdown("## 🏠 Operations Dashboard Home")
    st.caption("Real-time service health, metrics, and incident telemetry")
    
    # Initialize states for dashboard
    if "nginx_status" not in st.session_state:
        st.session_state.nginx_status = {"status": "UNKNOWN", "time": "Never"}
    if "sys_metrics" not in st.session_state:
        st.session_state.sys_metrics = {"cpu": "Unknown", "mem": "Unknown", "time": "Never"}

    # Service Health Row
    st.markdown("### 🚦 Service Health Status")
    h_col1, h_col2, h_col3 = st.columns(3)
    
    # Proxy status
    nginx_color = "#10b981" if st.session_state.nginx_status["status"] == "SUCCESS" else ("#ef4444" if st.session_state.nginx_status["status"] == "FAILED" else "#64748b")
    h_col1.markdown(
        f"""
        <div style="padding: 1rem; border-radius: 0.5rem; border: 1px solid {nginx_color}; background-color: rgba(16, 185, 129, 0.05); text-align: center;">
            <div style="font-size: 1.5rem;">🖥️ Proxy Service (Nginx)</div>
            <div style="color: {nginx_color}; font-weight: bold; margin-top: 0.5rem;">{st.session_state.nginx_status['status']}</div>
            <div style="font-size: 0.75rem; color: #64748b;">Last Checked: {st.session_state.nginx_status['time']}</div>
        </div>
        """,
        unsafe_allow_html=True
    )
    
    # Runner status
    runner_status = "🟢 IDLE READY" if st.session_state.run_state != "RUNNING" else "🔵 RUNNING EXECUTION"
    runner_bg = "rgba(16, 185, 129, 0.05)" if st.session_state.run_state != "RUNNING" else "rgba(59, 130, 246, 0.05)"
    runner_border = "#10b981" if st.session_state.run_state != "RUNNING" else "#3b82f6"
    h_col2.markdown(
        f"""
        <div style="padding: 1rem; border-radius: 0.5rem; border: 1px solid {runner_border}; background-color: {runner_bg}; text-align: center;">
            <div style="font-size: 1.5rem;">⚙️ Runner Engine</div>
            <div style="color: {runner_border}; font-weight: bold; margin-top: 0.5rem;">{runner_status}</div>
        </div>
        """,
        unsafe_allow_html=True
    )
    
    # DB status
    h_col3.markdown(
        """
        <div style="padding: 1rem; border-radius: 0.5rem; border: 1px solid #64748b; background-color: rgba(100, 116, 139, 0.05); text-align: center;">
            <div style="font-size: 1.5rem;">🗄️ System Database</div>
            <div style="color: #64748b; font-weight: bold; margin-top: 0.5rem;">Data Store: JSON Files (Local)</div>
        </div>
        """,
        unsafe_allow_html=True
    )
    
    st.markdown("---")
    
    # KPI Calculations
    stats = load_historical_stats()
    total_steps = stats["successful_steps"] + stats["failed_steps"]
    success_rate = (stats["successful_steps"] / total_steps * 100) if total_steps > 0 else 0.0
    pending_approvals = len(get_pending_runs())
    active_users = len(get_active_users())
    
    # Render KPI Cards
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Executions", stats["total_executions"])
    col2.metric("Success Rate %", f"{success_rate:.1f}%")
    col3.metric("Active Sessions", active_users)
    col4.metric("Pending Approvals", pending_approvals)
    
    st.markdown("---")
    
    # System Metrics (Memory/CPU usage)
    st.markdown("### 📊 Resource Telemetry")
    if st.button("🔄 Refresh Metrics & Nginx Status"):
        res_nginx = force_execute_step("Check current Nginx status")
        st.session_state.nginx_status = {
            "status": res_nginx["status"],
            "time": datetime.now().strftime("%H:%M:%S")
        }
        res_cpu = force_execute_step("Check CPU usage")
        res_mem = force_execute_step("Check memory usage")
        st.session_state.sys_metrics = {
            "cpu": res_cpu.get("output", "Failed"),
            "mem": res_mem.get("output", "Failed"),
            "time": datetime.now().strftime("%H:%M:%S")
        }
        st.rerun()

    r_col1, r_col2 = st.columns(2)
    with r_col1:
        st.markdown("**CPU Usage**")
        st.info(st.session_state.sys_metrics["cpu"])
    with r_col2:
        st.markdown("**Memory Usage**")
        st.info(st.session_state.sys_metrics["mem"])
    st.caption(f"Last Refreshed: {st.session_state.sys_metrics['time']}")
        
    st.markdown("---")
    
    # Chart
    st.markdown("### 📈 Operations Telemetry Trend")
    if stats["reports"]:
        trend_data = []
        for rep in stats["reports"]:
            ts = rep.get("timestamp", "")
            if ts:
                trend_data.append({
                    "Time": ts,
                    "Success": rep.get("summary", {}).get("success", 0),
                    "Failure": rep.get("summary", {}).get("failed", 0)
                })
        if trend_data:
            trend_df = pd.DataFrame(trend_data)
            trend_df["Time"] = pd.to_datetime(trend_df["Time"])
            trend_df = trend_df.sort_values("Time").set_index("Time")
            st.line_chart(trend_df, use_container_width=True)
        else:
            st.info("No executions yet. Run your first runbook.")
    else:
        st.info("No executions yet. Run your first runbook.")


# ----------------------------------------------------
# PAGE 2: 📋 RUNBOOKS
# ----------------------------------------------------
elif selected_page == "📋 Runbooks":
    st.markdown("## 📋 Runbook Operations Board")
    
    # Sidebar uploader and loaders
    st.sidebar.markdown("---")
    st.sidebar.markdown("### 📤 Load Runbook")
    uploaded_file = st.sidebar.file_uploader(
        "Choose a Markdown (.md) file",
        type=["md"]
    )
    
    st.sidebar.markdown("### 💡 Quick Sample Loaders")
    if st.sidebar.button("🔴 Nginx Recovery", use_container_width=True):
        st.session_state.runbook_source = "sample_nginx"
        st.session_state.runbook_content = None
        st.session_state.uploaded_file_name = "restart_nginx.md (Sample)"
        st.session_state.run_state = "IDLE"
        st.session_state.results = []
        st.session_state.waiting_for_approval = False
        st.session_state.report_path = None
        st.session_state.run_id = None
        st.session_state.timeline = []
        st.session_state.failures = []
        st.session_state.recommendations = []
        st.rerun()
        
    if st.sidebar.button("🟡 High CPU Incident", use_container_width=True):
        st.session_state.runbook_source = "sample_cpu"
        st.session_state.runbook_content = None
        st.session_state.uploaded_file_name = "high_cpu.md (Sample)"
        st.session_state.run_state = "IDLE"
        st.session_state.results = []
        st.session_state.waiting_for_approval = False
        st.session_state.report_path = None
        st.session_state.run_id = None
        st.session_state.timeline = []
        st.session_state.failures = []
        st.session_state.recommendations = []
        st.rerun()
        
    if st.sidebar.button("🟠 Disk Space Cleanup", use_container_width=True):
        st.session_state.runbook_source = "sample_disk"
        st.session_state.runbook_content = None
        st.session_state.uploaded_file_name = "disk_full.md (Sample)"
        st.session_state.run_state = "IDLE"
        st.session_state.results = []
        st.session_state.waiting_for_approval = False
        st.session_state.report_path = None
        st.session_state.run_id = None
        st.session_state.timeline = []
        st.session_state.failures = []
        st.session_state.recommendations = []
        st.rerun()

    if uploaded_file is not None:
        try:
            file_bytes = uploaded_file.getvalue()
            file_content = file_bytes.decode("utf-8")
            
            if (st.session_state.last_uploaded_name != uploaded_file.name or 
                st.session_state.last_uploaded_content != file_content):
                
                st.session_state.runbook_source = "upload"
                st.session_state.uploaded_file_name = uploaded_file.name
                st.session_state.runbook_content = file_content
                st.session_state.last_uploaded_name = uploaded_file.name
                st.session_state.last_uploaded_content = file_content
                
                st.session_state.run_state = "IDLE"
                st.session_state.results = []
                st.session_state.waiting_for_approval = False
                st.session_state.report_path = None
                st.session_state.run_id = None
                st.session_state.timeline = []
                st.session_state.failures = []
                st.session_state.recommendations = []
                st.rerun()
        except Exception as e:
            st.sidebar.error(f"Error reading file: {str(e)}")

    # Resolve runbook data
    runbook_data = None
    runbook_name = st.session_state.uploaded_file_name
    
    if st.session_state.runbook_source == "upload":
        if st.session_state.runbook_content:
            runbook_data = parse_runbook(st.session_state.runbook_content)
    elif st.session_state.runbook_source == "sample_nginx":
        path = os.path.join(base_dir, "runbooks", "restart_nginx.md")
        runbook_data = parse_runbook(path)
    elif st.session_state.runbook_source == "sample_cpu":
        path = os.path.join(base_dir, "runbooks", "high_cpu.md")
        runbook_data = parse_runbook(path)
    elif st.session_state.runbook_source == "sample_disk":
        path = os.path.join(base_dir, "runbooks", "disk_full.md")
        runbook_data = parse_runbook(path)

    # Embedded Manager Approval Desk
    if can_approve_risky_action(st.session_state.role):
        st.markdown("---")
        with st.expander("🔑 Manager Approval Desk", expanded=True):
            st.caption("Review and authorize safety-critical runbook actions")
            pending = get_pending_runs()
            if not pending:
                st.info("No runbook steps are currently pending approval.")
            else:
                st.markdown(f"Detected **{len(pending)}** execution session(s) awaiting authorization:")
                for run in pending:
                    st.markdown(
                        f"""
                        <div style="padding: 1rem; border-radius: 0.5rem; background-color: rgba(255, 165, 0, 0.05); border-left: 5px solid orange; margin-bottom: 1rem;">
                            <h4 style="margin:0; color: orange;">Runbook: {run['runbook_title']}</h4>
                            <p style="margin:0.2rem 0;"><strong>Run ID:</strong> <code>{run['run_id']}</code> | <strong>Operator:</strong> <code>{run['user']}</code></p>
                            <p style="margin:0.2rem 0;"><strong>Step Awaiting Authorization:</strong> <code>{run['step_name']}</code></p>
                            <p style="margin:0.2rem 0;"><strong>Action Command:</strong> <code>{run['command']}</code></p>
                        </div>
                        """,
                        unsafe_allow_html=True
                    )
                    col1, col2 = st.columns(2)
                    with col1:
                        if st.button("✅ Authorize Execution", key=f"appr_{run['run_id']}", type="primary", use_container_width=True):
                            write_audit_log(
                                st.session_state.username,
                                st.session_state.role,
                                "APPROVAL_ACTION",
                                step=run['step_name'],
                                status="APPROVED",
                                details=f"Authorized command execution for run {run['run_id']}."
                            )
                            run["status"] = "APPROVED"
                            save_active_run(run["run_id"], run)
                            st.success("Action authorized.")
                            st.rerun()
                    with col2:
                        if st.button("Skip Step Action", key=f"skip_{run['run_id']}", use_container_width=True):
                            write_audit_log(
                                st.session_state.username,
                                st.session_state.role,
                                "APPROVAL_ACTION",
                                step=run['step_name'],
                                status="SKIPPED",
                                details=f"Skipped command execution for run {run['run_id']}."
                            )
                            run["status"] = "SKIPPED"
                            save_active_run(run["run_id"], run)
                            st.info("Action skipped.")
                            st.rerun()

    if not runbook_data:
        st.info("👈 Please upload a runbook file or select a quick loader sample in the sidebar.")
    else:
        st.markdown("---")
        # Metadata Header
        st.markdown(
            f"""
            <div style="padding: 1.5rem; border-radius: 0.5rem; background-color: rgba(31, 119, 180, 0.08); border-left: 6px solid #1f77b4; margin-bottom: 1.5rem;">
                <h3 style="margin: 0 0 0.5rem 0; color: #1f77b4; font-weight: 600;">{runbook_data['title']}</h3>
                <p style="margin: 0; font-size: 1.1rem;"><strong>Objective:</strong> {runbook_data['objective']}</p>
                <p style="margin: 0; font-size: 0.95rem; color: #666666;">Source file: <code>{runbook_name}</code></p>
            </div>
            """,
            unsafe_allow_html=True
        )
        
        # Render steps
        st.markdown("#### Steps Checklist:")
        commands_map = runbook_data.get("commands", {})
        for i, step in enumerate(runbook_data["steps"], 1):
            cmd_info = f" (Executes: `{commands_map[step]}`)" if step in commands_map else " (No command mapped)"
            is_risky = step in RISKY_STEPS or any(word in step.lower() for word in ["restart", "clean", "delete", "remove", "stop"])
            icon = "⚠️" if is_risky else "⬜"
            st.markdown(f"{i}. {icon} **{step}**{cmd_info}")
            
        st.markdown("---")
        
        # Execution Panel
        st.markdown("### ⚡ Execution Panel")
        
        run_state = st.session_state.run_state
        results = st.session_state.results
        total_steps = len(runbook_data["steps"])
        is_developer = can_execute_runbook(st.session_state.role)
        
        if run_state == "IDLE":
            if not is_developer:
                st.warning("🔒 **Authorization Restricted:** Only users with the Developer role can execute runbooks directly. Managers are restricted to auditing and step approval tasks.")
            else:
                if st.button("▶ Execute Runbook", type="primary", use_container_width=True):
                    st.session_state.run_id = f"run_{int(time.time())}"
                    time_now = datetime.now().strftime("%H:%M")
                    st.session_state.timeline = [
                        f"{time_now} Login",
                        f"{time_now} Execute Runbook"
                    ]
                    st.session_state.run_state = "RUNNING"
                    st.session_state.results = []
                    st.session_state.waiting_for_approval = False
                    st.session_state.failures = []
                    st.session_state.recommendations = []
                    st.session_state.report_path = None
                    
                    write_audit_log(
                        st.session_state.username,
                        st.session_state.role,
                        "EXECUTE_RUNBOOK",
                        details=f"Initiated execution of runbook '{runbook_data['title']}' (Run ID: {st.session_state.run_id})."
                    )
                    st.rerun()
                    
        elif run_state in ["RUNNING", "COMPLETED"]:
            num_results = len(results)
            progress_val = min(1.0, num_results / total_steps) if total_steps > 0 else 1.0
            st.progress(progress_val)
            st.caption(f"Progress: {num_results} / {total_steps} steps completed")
            
            # Show completed results
            for res in results:
                step_name = res["step"]
                status = res["status"]
                cmd = res.get("command", "")
                out = res.get("output", "")
                
                if status == "SUCCESS":
                    st.success(f"✅ SUCCESS: {step_name}")
                    with st.expander(f"Command Details: {cmd}", expanded=False):
                        st.code(out, language="text")
                elif status == "FAILED":
                    st.error(f"❌ FAILED: {step_name}")
                    with st.expander(f"Command Details: {cmd}", expanded=False):
                        st.code(out, language="text")
                elif status == "SKIPPED":
                    st.info(f"⏭️ SKIPPED: {step_name}")
                    with st.expander("Details", expanded=False):
                        st.write(out)
                elif status == "BLOCKED":
                    st.warning(f"🚫 BLOCKED: {step_name}")
                    with st.expander("Details", expanded=False):
                        st.write(out)
            
            if run_state == "RUNNING":
                if st.session_state.waiting_for_approval:
                    st.warning(
                        f"⚠️ **Risky Step Pending Manager Approval: '{runbook_data['steps'][num_results]}'**\n\n"
                        f"Command: `{commands_map.get(runbook_data['steps'][num_results])}`\n\n"
                        f"Execution is paused. Please request a user with the Manager role to authorize this action on the **Manager Approval Desk**."
                    )
                    
                    import streamlit.components.v1 as components
                    components.html("<meta http-equiv='refresh' content='5'>", height=0)
                    st.info("⏳ Auto-polling for manager authorization every 5 seconds...")
                    
                    run_sync = load_active_run(st.session_state.run_id)
                    time_now = datetime.now().strftime("%H:%M")
                    
                    if run_sync and run_sync.get("status") == "APPROVED":
                        st.session_state.waiting_for_approval = False
                        st.session_state.timeline.append(f"{time_now} Manager Approved")
                        
                        current_step = runbook_data["steps"][num_results]
                        cmd_to_run = commands_map.get(current_step)
                        res = force_execute_step(current_step, command=cmd_to_run)
                        
                        if res["status"] == "SUCCESS":
                            st.session_state.timeline.append(f"{time_now} {current_step} SUCCESS")
                            write_audit_log(st.session_state.username, st.session_state.role, "EXECUTE_STEP", step=current_step, status="SUCCESS")
                        elif res["status"] == "SKIPPED":
                            st.session_state.timeline.append(f"{time_now} {current_step} SKIPPED")
                            write_audit_log(st.session_state.username, st.session_state.role, "EXECUTE_STEP", step=current_step, status="SKIPPED", details="Command not mapped")
                        else:
                            analysis = analyze_failure(current_step, cmd_to_run, res.get("returncode", -1), res.get("output", ""))
                            st.session_state.timeline.append(f"{time_now} {current_step} FAILED")
                            write_audit_log(st.session_state.username, st.session_state.role, "FAILED_EXECUTION", step=current_step, status="FAILED", details=analysis["root_cause"])
                            st.session_state.failures.append(analysis)
                            st.session_state.recommendations.append(analysis)
                            
                        st.session_state.results.append(res)
                        delete_active_run(st.session_state.run_id)
                        st.rerun()
                        
                    elif run_sync and run_sync.get("status") == "SKIPPED":
                        st.session_state.waiting_for_approval = False
                        st.session_state.timeline.append(f"{time_now} Manager Skipped")
                        st.session_state.timeline.append(f"{time_now} {runbook_data['steps'][num_results]} SKIPPED")
                        
                        st.session_state.results.append({
                            "step": runbook_data["steps"][num_results],
                            "status": "SKIPPED",
                            "output": "Skipped by Manager instruction.",
                            "returncode": 0
                        })
                        write_audit_log(st.session_state.username, st.session_state.role, "EXECUTE_STEP", step=runbook_data["steps"][num_results], status="SKIPPED")
                        delete_active_run(st.session_state.run_id)
                        st.rerun()
                else:
                    if num_results < total_steps:
                        next_step = runbook_data["steps"][num_results]
                        cmd_to_run = commands_map.get(next_step)
                        time_now = datetime.now().strftime("%H:%M")
                        
                        res = execute_step(next_step, command=cmd_to_run)
                        
                        if res["status"] == "BLOCKED":
                            write_audit_log(
                                st.session_state.username,
                                st.session_state.role,
                                "DENIED_ACCESS",
                                step=next_step,
                                status="BLOCKED",
                                details=f"Suspicious activity: unallowed command blocked. Command: {cmd_to_run}"
                            )
                            st.session_state.timeline.append(f"{time_now} {next_step} BLOCKED")
                            st.session_state.results.append(res)
                            st.rerun()
                            
                        elif res["status"] == "NEEDS_APPROVAL":
                            st.session_state.timeline.append(f"{time_now} {next_step} Approval Requested")
                            write_audit_log(
                                st.session_state.username,
                                st.session_state.role,
                                "APPROVAL_REQUEST",
                                step=next_step,
                                status="PENDING",
                                details=f"Risky step approval required. Command: {cmd_to_run}"
                            )
                            
                            run_data = {
                                "run_id": st.session_state.run_id,
                                "runbook_title": runbook_data["title"],
                                "user": st.session_state.username,
                                "current_step_idx": num_results,
                                "step_name": next_step,
                                "command": cmd_to_run,
                                "results": st.session_state.results,
                                "steps": runbook_data["steps"],
                                "commands": commands_map,
                                "timeline": st.session_state.timeline,
                                "failures": st.session_state.failures,
                                "recommendations": st.session_state.recommendations,
                                "status": "NEEDS_APPROVAL"
                            }
                            save_active_run(st.session_state.run_id, run_data)
                            st.session_state.waiting_for_approval = True
                            st.rerun()
                        else:
                            if res["status"] == "SUCCESS":
                                st.session_state.timeline.append(f"{time_now} {next_step} SUCCESS")
                                write_audit_log(st.session_state.username, st.session_state.role, "EXECUTE_STEP", step=next_step, status="SUCCESS")
                            elif res["status"] == "SKIPPED":
                                st.session_state.timeline.append(f"{time_now} {next_step} SKIPPED")
                                write_audit_log(st.session_state.username, st.session_state.role, "EXECUTE_STEP", step=next_step, status="SKIPPED", details="Command not mapped")
                            else:
                                analysis = analyze_failure(next_step, cmd_to_run, res.get("returncode", -1), res.get("output", ""))
                                st.session_state.timeline.append(f"{time_now} {next_step} FAILED")
                                write_audit_log(st.session_state.username, st.session_state.role, "FAILED_EXECUTION", step=next_step, status="FAILED", details=analysis["root_cause"])
                                st.session_state.failures.append(analysis)
                                st.session_state.recommendations.append(analysis)
                                
                            st.session_state.results.append(res)
                            st.rerun()
                    else:
                        st.session_state.run_state = "COMPLETED"
                        session_audit = [log for log in read_audit_logs() if log.get("user") == st.session_state.username]
                        
                        rep_path = generate_report(
                            runbook_title=runbook_data["title"],
                            results=st.session_state.results,
                            user=st.session_state.username,
                            role=st.session_state.role,
                            timeline=st.session_state.timeline,
                            audit_trail=session_audit,
                            failures=st.session_state.failures,
                            recommendations=st.session_state.recommendations
                        )
                        st.session_state.report_path = rep_path
                        write_audit_log(
                            st.session_state.username,
                            st.session_state.role,
                            "REPORT_GENERATION",
                            details=f"Generated JSON incident report: {os.path.basename(rep_path)}"
                        )
                        st.rerun()
            
            if run_state == "COMPLETED":
                if st.session_state.report_path and os.path.exists(st.session_state.report_path):
                    try:
                        with open(st.session_state.report_path, "r", encoding="utf-8") as rf:
                            report_json = rf.read()
                        st.download_button(
                            label="📥 Download JSON Report",
                            data=report_json,
                            file_name=os.path.basename(st.session_state.report_path),
                            mime="application/json",
                            use_container_width=True
                        )
                    except Exception as e:
                        st.error(f"Failed to read report: {str(e)}")
                
                if st.button("🔄 Reset Execution", use_container_width=True):
                    st.session_state.run_state = "IDLE"
                    st.session_state.results = []
                    st.session_state.waiting_for_approval = False
                    st.session_state.report_path = None
                    st.session_state.run_id = None
                    st.session_state.timeline = []
                    st.session_state.failures = []
                    st.session_state.recommendations = []
                    st.rerun()

        # Render Chronological Timeline & Diagnostics/Recovery ALWAYS below checklist
        st.markdown("---")
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("### 📅 Chronological Timeline")
            if st.session_state.timeline:
                for event in st.session_state.timeline:
                    st.markdown(f"🕒 `{event}`")
            else:
                st.caption("No events recorded yet for this session.")
                
        with col2:
            st.markdown("### 🛠️ Diagnostics & Recovery Actions")
            if st.session_state.recommendations:
                for rec in st.session_state.recommendations:
                    st.error(
                        f"**Failed Step:** {rec['failure']}\n\n"
                        f"**Severity:** `{rec['severity']}`\n\n"
                        f"**Root Cause:** {rec['root_cause']}\n\n"
                        f"**Recommendation:** {rec['recommendation']}"
                    )
            else:
                if run_state == "COMPLETED":
                    st.success("🎉 Run completed with zero execution errors!")
                elif run_state == "RUNNING":
                    st.success("🎉 Run in progress with zero execution errors so far.")
                else:
                    st.info("No diagnostics captured. Run the execution engine to analyze system failures.")

# ----------------------------------------------------
# PAGE 3: 🕵️ AUDIT LOGS
# ----------------------------------------------------
elif selected_page == "🕵️ Audit Logs":
    st.markdown("## 🕵️ Security Audit Dashboard")
    st.caption("Immutable system operation trails and annotation panel")
    
    logs = read_audit_logs()
    
    if not logs:
        st.info("No audit logs recorded.")
    else:
        def get_log_severity(log) -> str:
            action = log.get("action", "")
            status = log.get("status", "")
            if action in ["FAILED_LOGIN", "DENIED_ACCESS", "FAILED_EXECUTION"] or status in ["BLOCKED", "FAILED"]:
                return "CRITICAL"
            elif action in ["APPROVAL_REQUEST", "APPROVAL_ACTION"]:
                return "WARNING"
            return "INFO"

        annotations = load_audit_annotations()
        total_logs = len(logs)
        critical_logs = sum(1 for log in logs if get_log_severity(log) == "CRITICAL")
        failed_logs = sum(1 for log in logs if log.get("status") == "FAILED" or log.get("action") == "FAILED_LOGIN")
        annotated_logs = sum(1 for log in logs if annotations.get(f"{log.get('timestamp')}_{log.get('user')}_{log.get('action')}"))
        
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Total Logs", total_logs)
        col2.metric("⚠️ Critical Logs", critical_logs)
        col3.metric("❌ Failed Steps", failed_logs)
        col4.metric("💬 Annotated Logs", annotated_logs)
        
        st.markdown("---")
        
        f_col1, f_col2, f_col3 = st.columns(3)
        with f_col1:
            status_filter = st.selectbox("Filter Status", ["ALL", "SUCCESS", "FAILED", "BLOCKED", "PENDING"])
        with f_col2:
            severity_filter = st.selectbox("Filter Severity", ["ALL", "INFO", "WARNING", "CRITICAL"])
        with f_col3:
            search_query = st.text_input("🔍 Search log details...", "")
            
        processed_logs = []
        for log in logs:
            log_key = f"{log.get('timestamp')}_{log.get('user')}_{log.get('action')}"
            processed_log = log.copy()
            processed_log["severity"] = get_log_severity(log)
            ann_list = annotations.get(log_key, [])
            processed_log["annotation"] = f"{len(ann_list)} notes" if ann_list else ""
            processed_logs.append(processed_log)
            
        df = pd.DataFrame(processed_logs)
        filtered_df = df.copy()
        if status_filter != "ALL":
            filtered_df = filtered_df[filtered_df["status"] == status_filter]
        if severity_filter != "ALL":
            filtered_df = filtered_df[filtered_df["severity"] == severity_filter]
        if search_query:
            query = search_query.lower()
            filtered_df = filtered_df[
                filtered_df["details"].str.lower().str.contains(query) |
                filtered_df["user"].str.lower().str.contains(query) |
                filtered_df["action"].str.lower().str.contains(query)
            ]
            
        filtered_df = filtered_df.iloc[::-1]
        
        st.markdown("### 📋 Audit Logs Table")
        st.dataframe(
            filtered_df[["timestamp", "severity", "user", "role", "action", "status", "details", "annotation"]],
            column_config={
                "timestamp": "Timestamp",
                "severity": "Severity",
                "user": "User",
                "role": "Role",
                "action": "Action Code",
                "status": "Status",
                "details": "Details Log",
                "annotation": "Annotation"
            },
            use_container_width=True,
            hide_index=True
        )
        
        st.markdown("### 💬 Log Row Annotations & Expanders")
        limit = 50
        count = 0
        for idx, row in filtered_df.iterrows():
            if count >= limit:
                st.caption(f"Showing top {limit} entries. Refine search filters for older entries.")
                break
                
            log_key = f"{row['timestamp']}_{row['user']}_{row['action']}"
            severity_icon = "🔴" if row["severity"] == "CRITICAL" else ("🟡" if row["severity"] == "WARNING" else "🔵")
            status_icon = "✅" if row["status"] == "SUCCESS" else ("❌" if row["status"] == "FAILED" else ("🚫" if row["status"] == "BLOCKED" else "⏳"))
            
            exp_title = f"{severity_icon} [{row['severity']}] {row['timestamp']} | {row['user']} | Action: {row['action']} ({status_icon} {row['status']})"
            with st.expander(exp_title):
                st.markdown(f"**Detailed Message:** {row['details']}")
                st.markdown(f"**Operator Role:** `{row['role']}`")
                
                ann_list = annotations.get(log_key, [])
                if ann_list:
                    st.write("**Annotation History:**")
                    for c in ann_list:
                        st.markdown(f"💬 **{c['username']}** *({c['timestamp']})*: {c['comment']}")
                else:
                    st.caption("No annotations recorded yet.")
                
                st.markdown("---")
                new_comment = st.text_input("Add new annotation:", key=f"ann_input_{log_key}_{idx}")
                if st.button("Save Annotation", key=f"ann_btn_{log_key}_{idx}"):
                    if new_comment.strip():
                        update_audit_comment(log_key, st.session_state.username, new_comment.strip(), datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
                        st.success("Annotation successfully saved.")
                        st.rerun()
            count += 1

# ----------------------------------------------------
# PAGE 4: 👥 ACTIVE USERS
# ----------------------------------------------------
elif selected_page == "👥 Active Users":
    if not can_view_active_users(st.session_state.role):
        st.error("🔒 **Access Denied:** Only users logged in with the Manager role can access the Active Operator sessions registry.")
    else:
        st.markdown("## 👥 Active Operator Sessions")
        st.caption("Real-time telemetry of logged-in sessions")
        
        users = get_active_users()
        if not users:
            st.info("No active users found.")
        else:
            df = pd.DataFrame(users)
            st.dataframe(
                df,
                column_config={
                    "username": "Username",
                    "role": "Role",
                    "login_time": "Logged In At",
                    "last_activity": "Last Activity At"
                },
                use_container_width=True,
                hide_index=True
            )

# ----------------------------------------------------
# PAGE 5: 📊 REPORTS
# ----------------------------------------------------
elif selected_page == "📊 Reports":
    st.markdown("## 📊 Incident Reports Directory")
    st.caption("Compiled records of historical execution sessions")
    
    reports_dir = os.path.join(base_dir, "reports")
    if not os.path.exists(reports_dir):
        os.makedirs(reports_dir, exist_ok=True)
        
    files = [f for f in os.listdir(reports_dir) if f.endswith(".json")]
    
    if not files:
        st.info("No JSON execution reports found. Run a runbook to generate reports.")
    else:
        st.markdown(f"Detected **{len(files)}** compiled execution report(s):")
        
        reports_data = []
        for f in files:
            try:
                with open(os.path.join(reports_dir, f), "r", encoding="utf-8") as rf:
                    rep = json.load(rf)
                    reports_data.append({
                        "file_name": f,
                        "runbook": rep.get("runbook", "Unknown"),
                        "timestamp": rep.get("timestamp", "Unknown"),
                        "operator": rep.get("operator", {}).get("user", "Unknown"),
                        "role": rep.get("operator", {}).get("role", "Unknown"),
                        "success": rep.get("summary", {}).get("success", 0),
                        "failed": rep.get("summary", {}).get("failed", 0),
                        "total": rep.get("summary", {}).get("total", 0)
                    })
            except Exception:
                pass
                
        df_reports = pd.DataFrame(reports_data)
        st.dataframe(
            df_reports[["timestamp", "runbook", "operator", "role", "success", "failed", "total", "file_name"]],
            column_config={
                "timestamp": "Timestamp",
                "runbook": "Runbook Title",
                "operator": "Operator",
                "role": "Role",
                "success": "Success",
                "failed": "Failed",
                "total": "Total Steps",
                "file_name": "Report Filename"
            },
            use_container_width=True,
            hide_index=True
        )
        
        st.markdown("### 📥 Download & Preview Specific Reports")
        selected_file = st.selectbox("Select Report file to view/download", files)
        if selected_file:
            try:
                with open(os.path.join(reports_dir, selected_file), "r", encoding="utf-8") as rf:
                    report_content = rf.read()
                    rep_json = json.loads(report_content)
                
                st.markdown("#### 📄 Report Preview")
                r_col1, r_col2 = st.columns(2)
                r_col1.markdown(f"**Runbook:** {rep_json.get('runbook', 'Unknown')}")
                r_col1.markdown(f"**Date:** {rep_json.get('timestamp', 'Unknown')}")
                r_col2.markdown(f"**Operator:** {rep_json.get('operator', {}).get('user', 'Unknown')} ({rep_json.get('operator', {}).get('role', 'Unknown')})")
                r_col2.markdown(f"**Run ID:** {rep_json.get('run_id', 'Unknown')}")
                
                st.markdown("**Timeline:**")
                for t in rep_json.get("timeline", []):
                    st.caption(f"• {t}")
                    
                st.markdown("**Step Results:**")
                for res in rep_json.get("results", []):
                    icon = "✅" if res.get("status") == "SUCCESS" else ("⏭️" if res.get("status") == "SKIPPED" else "❌")
                    st.markdown(f"{icon} **{res.get('step', 'Unknown Step')}**")
                    if res.get("status") != "SUCCESS" and "output" in res:
                        with st.expander("Show Output / Error"):
                            st.code(res.get("output"), language="text")

                st.markdown("---")
                st.download_button(
                    label="📥 Download Selected Report JSON",
                    data=report_content,
                    file_name=selected_file,
                    mime="application/json",
                    use_container_width=True
                )
            except Exception as e:
                st.error(f"Error reading report: {str(e)}")

# ----------------------------------------------------
# PAGE 6: 📅 INCIDENT TIMELINE
# ----------------------------------------------------
elif selected_page == "📅 Incident Timeline":
    st.markdown("## 📅 System Incident Timeline Feed")
    st.caption("Aggregated security and operational event trail")
    
    logs = read_audit_logs()
    
    if not logs:
        st.info("No system events logged in the audit trail.")
    else:
        st.markdown("### 🕒 Real-time Operations Feed")
        sorted_logs = sorted(logs, key=lambda x: x.get("timestamp", ""), reverse=True)
        
        for idx, log in enumerate(sorted_logs[:100]):
            action = log.get("action", "")
            user = log.get("user", "System")
            role = log.get("role", "")
            timestamp = log.get("timestamp", "")
            step = log.get("step", "")
            status = log.get("status", "")
            details = log.get("details", "")
            
            icon = "📝"
            color = "#64748b"
            
            if action == "LOGIN":
                icon = "🔑"
                color = "#10b981"
            elif action == "FAILED_LOGIN":
                icon = "🚨"
                color = "#ef4444"
            elif action in ["TIMEOUT_LOGOUT", "LOGOUT"]:
                icon = "🔓"
                color = "#f59e0b"
            elif action == "EXECUTE_RUNBOOK":
                icon = "🚀"
                color = "#3b82f6"
            elif action == "APPROVAL_REQUEST":
                icon = "⚠️"
                color = "#f59e0b"
            elif action == "APPROVAL_ACTION":
                icon = "✍️"
                color = "#8b5cf6"
            elif action == "DENIED_ACCESS":
                icon = "🚫"
                color = "#ef4444"
            elif action == "EXECUTE_STEP":
                if status == "SUCCESS":
                    icon = "✅"
                    color = "#10b981"
                elif status == "SKIPPED":
                    icon = "⏭️"
                    color = "#64748b"
            elif action == "FAILED_EXECUTION":
                icon = "❌"
                color = "#ef4444"
                
            step_info = f" | Step: `{step}`" if step else ""
            status_badge = f" [{status}]" if status else ""
            
            st.markdown(
                f"""
                <div style="padding: 1rem; margin-bottom: 0.8rem; border-radius: 0.5rem; border: 1px solid {color}; border-left: 6px solid {color}; background-color: rgba(0, 0, 0, 0.02);">
                    <div style="display: flex; justify-content: space-between; align-items: center;">
                        <span style="font-weight: 600; font-size: 1.05rem;">{icon} {action}{status_badge}</span>
                        <span style="font-size: 0.85rem; color: #64748b;">⏳ {timestamp}</span>
                    </div>
                    <div style="margin-top: 0.4rem; font-size: 0.95rem;">
                        <strong>Operator:</strong> <code>{user} ({role})</code>{step_info}
                    </div>
                    <div style="margin-top: 0.2rem; font-size: 0.9rem; color: #475569; font-style: italic;">
                        {details}
                    </div>
                </div>
                """,
                unsafe_allow_html=True
            )

# ----------------------------------------------------
# PAGE 7: 🛠️ FAILURE ANALYSIS
# ----------------------------------------------------
elif selected_page == "🛠️ Failure Analysis":
    st.markdown("## 🛠️ Diagnostics & Issue Center")
    st.caption("Historical analysis of non-zero subprocess execution exits")
    
    failures = get_failures()
    
    if not failures:
        st.success("🎉 No service execution failures currently recorded in database.")
    else:
        total_f = len(failures)
        high_f = sum(1 for f in failures if f.get("severity") == "HIGH")
        medium_f = sum(1 for f in failures if f.get("severity") == "MEDIUM")
        low_f = sum(1 for f in failures if f.get("severity") == "LOW")
        
        f_col1, f_col2, f_col3, f_col4 = st.columns(4)
        f_col1.metric("Total Failures", total_f)
        f_col2.metric("🔴 High Severity", high_f)
        f_col3.metric("🟡 Medium Severity", medium_f)
        f_col4.metric("🔵 Low Severity", low_f)
        
        st.markdown("---")
        severity_f = st.selectbox("Filter Failure Severity", ["ALL", "HIGH", "MEDIUM", "LOW"])
        search_f = st.text_input("🔍 Search root causes / stderr...", "")
        
        df_failures = pd.DataFrame(failures)
        filtered_f = df_failures.copy()
        if severity_f != "ALL":
            filtered_f = filtered_f[filtered_f["severity"] == severity_f]
        if search_f:
            q = search_f.lower()
            
            def safe_contains(col):
                return filtered_f[col].fillna("").astype(str).str.lower().str.contains(q)
                
            filtered_f = filtered_f[
                safe_contains("failure") |
                safe_contains("root_cause") |
                safe_contains("recommendation") |
                safe_contains("stderr")
            ]
            
        filtered_f = filtered_f.iloc[::-1]
        
        st.markdown("### 📋 Failure Diagnostics Log")
        if filtered_f.empty:
            st.info("No failures match the applied filters.")
        else:
            for idx, row in filtered_f.iterrows():
                severity_icon = "🔴" if row["severity"] == "HIGH" else ("🟡" if row["severity"] == "MEDIUM" else "🔵")
                timestamp = row.get("timestamp", "Unknown Time")
                failure_msg = row.get("failure", "Unknown Failure")
                exp_title = f"{severity_icon} [{row['severity']}] {timestamp} | {failure_msg}"
                
                with st.expander(exp_title):
                    st.markdown(f"**Root Cause Analysis:** {row.get('root_cause', '')}")
                    st.markdown(f"**Recovery Action:** {row.get('recommendation', '')}")
                    st.markdown("**Captured `stderr`:**")
                    st.code(row.get('stderr', 'No stderr output captured.'), language="text")
