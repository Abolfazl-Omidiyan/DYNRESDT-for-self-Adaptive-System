import sys
import os
import traceback

# Add current directory to path so imports work correctly
sys.path.insert(0, os.path.dirname(__file__))

def debugging_application(environ, start_response):
    try:
        from app import application
        return application(environ, start_response)
    except Exception as e:
        # Write traceback to a log file in the same directory for inspection
        log_file = os.path.join(os.path.dirname(__file__), 'passenger_error.log')
        try:
            with open(log_file, 'a') as f:
                f.write("--- ERROR OCCURRED ---\n")
                traceback.print_exc(file=f)
        except:
            pass
            
        # Format a user-friendly debug screen with the exact traceback
        tb_str = traceback.format_exc()
        start_response('500 Internal Server Error', [('Content-Type', 'text/html; charset=utf-8')])
        html = f"""
        <html>
        <head>
            <title>Python Application Setup Error</title>
            <style>
                body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; background-color: #fcfcfd; color: #1e293b; padding: 40px; line-height: 1.6; }}
                .container {{ max-width: 800px; margin: 0 auto; background: white; padding: 32px; border-radius: 12px; box-shadow: 0 4px 6px -1px rgb(0 0 0 / 0.1); border: 1px solid #e2e8f0; }}
                h1 {{ color: #dc2626; font-size: 24px; font-weight: 700; margin-top: 0; }}
                pre {{ background-color: #f8fafc; border: 1px solid #cbd5e1; padding: 16px; border-radius: 8px; overflow-x: auto; font-family: "JetBrains Mono", monospace; font-size: 13px; color: #0f172a; }}
                ul {{ background: #f1f5f9; padding: 16px 16px 16px 36px; border-radius: 8px; list-style-type: square; font-size: 14px; }}
                li {{ margin-bottom: 8px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <h1>Python Application Setup Error</h1>
                <p>An error occurred while importing or running <code>app.py</code>. This is common during first-time deployment on Passenger servers.</p>
                <p><strong>Traceback Details:</strong></p>
                <pre>{tb_str}</pre>
                <p><strong>Environment Information:</strong></p>
                <ul>
                    <li><strong>Python Version:</strong> {sys.version}</li>
                    <li><strong>Working Directory:</strong> {os.getcwd()}</li>
                    <li><strong>Script File:</strong> {__file__}</li>
                    <li><strong>System Path:</strong> {sys.path}</li>
                </ul>
                <p style="font-size: 13px; color: #64748b; margin-top: 24px; text-align: center;">DYNRESDT Self-Adaptive Digital Twin • Deployment Diagnostics</p>
            </div>
        </body>
        </html>
        """
        return [html.encode('utf-8')]

# Expose the wrapper as 'application' for Phusion Passenger
application = debugging_application

