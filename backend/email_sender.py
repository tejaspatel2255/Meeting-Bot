import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import os
import datetime

def send_bot_joined_notification(to_email: str, platform: str, meeting_id: str):
    sender = os.getenv("EMAIL_SENDER")
    password = os.getenv("EMAIL_PASSWORD")
    if not sender or not password:
        print("[Email Sender] Skip: EMAIL_SENDER or EMAIL_PASSWORD not configured.", flush=True)
        return
        
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"VibeNote Bot Joined Your {platform} Meeting"
        msg["From"] = sender
        msg["To"] = to_email
        
        body = f"VibeNote Bot has joined your {platform} meeting.\n\nYou can view the live dashboard at http://localhost:5000"
        msg.attach(MIMEText(body, "plain"))
        
        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        server.login(sender, password)
        server.sendmail(sender, to_email, msg.as_string())
        server.quit()
        print(f"[Email Sender] Bot joined notification sent successfully to {to_email}", flush=True)
    except Exception as e:
        print(f"[Email Sender] Failed to send bot joined email: {e}", flush=True)

def send_meeting_report(to_email: str, summary: dict, meeting_id: str):
    sender = os.getenv("EMAIL_SENDER")
    password = os.getenv("EMAIL_PASSWORD")
    if not sender or not password:
        print("[Email Sender] Skip: EMAIL_SENDER or EMAIL_PASSWORD not configured.", flush=True)
        return
        
    try:
        # Extract variables from summary dict
        meeting_summary = summary.get("summary", "No summary available.")
        sentiment = summary.get("overall_sentiment", "Neutral")
        topics = summary.get("key_topics", [])
        decisions = summary.get("decisions", [])
        action_items = summary.get("action_items", [])
        insights = summary.get("emotional_insights", [])
        
        date_str = datetime.datetime.now().strftime("%B %d, %Y - %I:%M %p")
        
        # Color coding for sentiment
        sentiment_bg = "#22c55e" # Green
        if sentiment.lower() in ["negative", "stressed", "urgent", "concerned"]:
            sentiment_bg = "#ef4444" # Red
        elif sentiment.lower() in ["mixed", "neutral"]:
            sentiment_bg = "#f59e0b" # Amber
            
        # Build HTML Body
        html = f"""
        <html>
        <body style="background-color: #0f0f0f; color: #f1f5f9; font-family: 'Outfit', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; padding: 20px; margin: 0;">
            <div style="max-width: 600px; margin: 0 auto; background-color: #191b26; border: 1px solid rgba(99, 102, 241, 0.2); border-radius: 12px; overflow: hidden; box-shadow: 0 10px 25px rgba(0,0,0,0.5);">
                <!-- Header -->
                <div style="background-color: #1e1b4b; padding: 25px; border-bottom: 2px solid #6366f1; text-align: center;">
                    <h1 style="color: #ffffff; margin: 0; font-size: 24px; font-weight: 700; letter-spacing: 0.5px;">VibeNote Meeting Report</h1>
                    <p style="color: #94a3b8; margin: 5px 0 0 0; font-size: 14px;">{date_str}</p>
                </div>
                
                <!-- Content Area -->
                <div style="padding: 25px;">
                    <!-- Section 1: Summary -->
                    <div style="margin-bottom: 25px;">
                        <h3 style="color: #6366f1; border-bottom: 1px solid rgba(255,255,255,0.1); padding-bottom: 5px; margin-top: 0;">Meeting Summary</h3>
                        <p style="color: #cbd5e1; font-size: 15px; line-height: 1.6;">{meeting_summary}</p>
                    </div>
                    
                    <!-- Section 2: Sentiment -->
                    <div style="margin-bottom: 25px; display: inline-block;">
                        <h3 style="color: #6366f1; border-bottom: 1px solid rgba(255,255,255,0.1); padding-bottom: 5px; margin-top: 0; display: block;">Overall Sentiment</h3>
                        <span style="display: inline-block; background-color: {sentiment_bg}; color: #ffffff; padding: 6px 14px; border-radius: 20px; font-size: 14px; font-weight: bold; text-transform: uppercase; letter-spacing: 0.5px;">
                            {sentiment}
                        </span>
                    </div>
        """
        
        # Section 3: Key Topics
        if topics:
            topics_html = "".join([f'<span style="display: inline-block; background-color: #2e303f; border: 1px solid rgba(99, 102, 241, 0.3); color: #cbd5e1; padding: 5px 12px; border-radius: 15px; font-size: 13px; margin: 4px 6px 4px 0;">{t}</span>' for t in topics])
            html += f"""
                    <div style="margin-bottom: 25px; margin-top: 15px;">
                        <h3 style="color: #6366f1; border-bottom: 1px solid rgba(255,255,255,0.1); padding-bottom: 5px; margin-top: 0;">Key Topics</h3>
                        <div style="margin-top: 10px;">{topics_html}</div>
                    </div>
            """
            
        # Section 4: Decisions
        if decisions:
            decisions_html = "".join([f'<li style="color: #cbd5e1; margin-bottom: 8px; font-size: 14px;">{d}</li>' for d in decisions])
            html += f"""
                    <div style="margin-bottom: 25px;">
                        <h3 style="color: #6366f1; border-bottom: 1px solid rgba(255,255,255,0.1); padding-bottom: 5px; margin-top: 0;">Decisions</h3>
                        <ol style="padding-left: 20px; margin-top: 10px;">{decisions_html}</ol>
                    </div>
            """
            
        # Section 5: Action Items
        if action_items:
            action_rows = ""
            for item in action_items:
                owner = item.get("owner", "N/A")
                task = item.get("task", "N/A")
                deadline = item.get("deadline", "N/A")
                action_rows += f"""
                <tr style="border-bottom: 1px solid rgba(255,255,255,0.05);">
                    <td style="padding: 10px; font-size: 14px; color: #ffffff; font-weight: 600;">{owner}</td>
                    <td style="padding: 10px; font-size: 14px; color: #cbd5e1;">{task}</td>
                    <td style="padding: 10px; font-size: 14px; color: #94a3b8; font-style: italic;">{deadline}</td>
                </tr>
                """
                
            html += f"""
                    <div style="margin-bottom: 25px;">
                        <h3 style="color: #6366f1; border-bottom: 1px solid rgba(255,255,255,0.1); padding-bottom: 5px; margin-top: 0;">Action Items</h3>
                        <table style="width: 100%; border-collapse: collapse; margin-top: 10px; background-color: #1e202c; border-radius: 8px; overflow: hidden;">
                            <thead>
                                <tr style="background-color: #2e303f; border-bottom: 2px solid #6366f1;">
                                    <th style="padding: 10px; text-align: left; font-size: 13px; color: #6366f1; text-transform: uppercase;">Owner</th>
                                    <th style="padding: 10px; text-align: left; font-size: 13px; color: #6366f1; text-transform: uppercase;">Task</th>
                                    <th style="padding: 10px; text-align: left; font-size: 13px; color: #6366f1; text-transform: uppercase;">Deadline</th>
                                </tr>
                            </thead>
                            <tbody>
                                {action_rows}
                            </tbody>
                        </table>
                    </div>
            """
            
        # Section 6: Emotional Insights
        if insights:
            insights_html = "".join([f'<li style="color: #cbd5e1; margin-bottom: 8px; font-size: 14px;">{ins}</li>' for ins in insights])
            html += f"""
                    <div style="margin-bottom: 25px;">
                        <h3 style="color: #6366f1; border-bottom: 1px solid rgba(255,255,255,0.1); padding-bottom: 5px; margin-top: 0;">Emotional Insights</h3>
                        <ul style="padding-left: 20px; margin-top: 10px;">{insights_html}</ul>
                    </div>
            """
            
        # Footer
        html += """
                </div>
                <div style="background-color: #12131a; padding: 20px; text-align: center; border-top: 1px solid rgba(255,255,255,0.05);">
                    <p style="color: #64748b; margin: 0; font-size: 12px; font-weight: 500;">Generated by VibeNote — AI Meeting Assistant</p>
                </div>
            </div>
        </body>
        </html>
        """
        
        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"Your VibeNote AI Meeting Analysis"
        msg["From"] = sender
        msg["To"] = to_email
        msg.attach(MIMEText(html, "html"))
        
        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        server.login(sender, password)
        server.sendmail(sender, to_email, msg.as_string())
        server.quit()
        print(f"[Email Sender] Post-meeting report successfully emailed to {to_email}", flush=True)
    except Exception as e:
        print(f"[Email Sender] Failed to send post-meeting email report: {e}", flush=True)
