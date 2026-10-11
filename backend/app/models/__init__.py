"""Import all models so SQLAlchemy + Alembic can discover them."""
from app.models.base import BaseModel, GUID, gen_uuid  # noqa: F401
from app.models.organisation import Organisation  # noqa: F401
from app.models.user import User, user_district, user_lab  # noqa: F401
from app.models.geography import State, District, School, Principal  # noqa: F401
from app.models.masters import (  # noqa: F401
    AcademicYear, Sector, JobRole, SocialCategory,
)
from app.models.lab import (  # noqa: F401
    Lab, Module, Unit, Session, Trainer,
)
from app.models.student import StudentPromotion, Student, Assessment  # noqa: F401
from app.models.operations import (  # noqa: F401
    DailyAttendance, AttendanceStudentMark, VTIssue, FieldVisit,
    FieldVisitStudentMark, GuestLecture, GuestLectureStudentMark,
    ClassAttendance, ClassAttendanceStudentMark, PrincipalIssue, OrgIssue, DeptIssue, MonthlyAttendanceReport, LabEquipment, EquipmentMaintenance,
)
from app.models.internship import (  # noqa: F401
    Employer, EmployerStudentMap, DailyDiary, OJTPlacement,
)
from app.models.misc import Feedback, Notification, AuditLog  # noqa: F401
from app.models.trainer_profile import (  # noqa: F401
    TrainerQualification, TrainerExperience, TrainerTraining, TrainerPosting,
    PrincipalQualification, PrincipalTraining, PrincipalPosting,
)
