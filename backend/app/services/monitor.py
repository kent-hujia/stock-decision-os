from app.services.finmind import finmind_service
from app.models.database import SessionLocal
from app.models.schemas import Thesis
from sqlalchemy import and_
import logging

class ThesisMonitorService:
    def __init__(self):
        self.finmind = finmind_service

    def check_all_active_theses(self):
        """
        Iterate through all active hypotheses and check if current market data triggers a failure.
        """
        db = SessionLocal()
        try:
            active_theses = db.query(Thesis).filter(Thesis.is_active == True).all()

            for thesis in active_theses:
                # This is a simplified trigger logic.
                # In production, we'd map trigger_metric to a specific FinMind endpoint.
                if thesis.trigger_metric == "revenue_yoy":
                    # Simulate checking latest revenue data
                    # current_val = self.finmind.get_latest_revenue_yoy(thesis.decision.ticker)
                    current_val = 0.05 # Simulated
                    if current_val < thesis.trigger_value:
                        self._trigger_alert(thesis, current_val)

                elif thesis.trigger_metric == "institutional_flow":
                    # Simulate checking institutional flow
                    current_val = -100000 # Simulated net sell
                    if current_val < thesis.trigger_value:
                        self._trigger_alert(thesis, current_val)

            db.commit()
        except Exception as e:
            logging.error(f"Thesis Monitoring Error: {e}")
        finally:
            db.close()

    def _trigger_alert(self, thesis: Thesis, current_val: float):
        """
        Trigger a notification to the user.
        """
        print(f"ALERT: Hypothesis failed for Decision {thesis.decision_id}!")
        print(f"Hypothesis: {thesis.hypothesis}")
        print(f"Trigger: {thesis.trigger_metric} < {thesis.trigger_value}, Actual: {current_val}")
        # In production, this would send a WebSocket notification or Email/Push.

monitor_service = ThesisMonitorService()
