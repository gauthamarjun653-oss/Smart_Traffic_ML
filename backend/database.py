import os
from datetime import datetime
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# Database path Setup
DB_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE_URL = f"sqlite:///{os.path.join(DB_DIR, 'traffic_violations.db')}"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class Violation(Base):
    __tablename__ = "violations"

    id = Column(Integer, primary_key=True, index=True)
    violation_type = Column(String, index=True)  # 'Overspeeding', 'No Helmet', 'Accident'
    timestamp = Column(DateTime, default=datetime.utcnow)
    vehicle_id = Column(Integer, nullable=True)
    vehicle_type = Column(String, nullable=True)  # 'car', 'motorcycle', 'bus', 'truck'
    speed = Column(Float, nullable=True)
    screenshot_path = Column(String)  # Relative path to served folder
    status = Column(String, default="Pending")

def init_db():
    Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
