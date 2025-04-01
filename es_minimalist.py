import datetime as dt
import functools
import unittest
import uuid

utc_now = functools.partial(dt.datetime.now, tz=dt.UTC)


def create_id(name):
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, str(name)))


class DomainEvent:
    def __init__(
        self,
        event_name: str,
        tags: dict | None = None,
        metadata: dict | None = None,
        event_id: str | None = None,
        stored_at: dt.datetime | None = None,
    ):
        self.event_name = event_name
        self.tags = tags or {}
        self.metadata = metadata or {}
        self.event_id = event_id or str(utc_now().timestamp())
        self.stored_at = stored_at or utc_now()
        self.details = {}

    def __getitem__(self, item):
        if item not in self.tags:
            return None
        return self.tags[item]

    def get_details(self):
        return dict(type=self.event_name, data=self.tags)


class CourseCreated(DomainEvent):
    def __init__(self, course_name: str, capacity: int):
        self.course_name = course_name
        self.capacity = capacity
        self.course_id: str = create_id(course_name)
        super().__init__(event_name="course_created")
        self.tags |= dict(
            course_id=self.course_id,
            course_name=self.course_name,
        )
        self.details = dict(course_name=course_name, capacity=capacity)


slice_tests = []
event_log = []


def create_course(history: list[DomainEvent], command):
    for event in history:
        if isinstance(event, CourseCreated) and event.course_name == command['name']:
            raise ValueError("Course name already exists")
    return CourseCreated(course_name=command["name"], capacity=command["capacity"])


slice_tests.append(
    {
        "test_function": create_course,
        "timelines": [
            {
                "timeline_name": "Happy path",
                "checkpoints": [
                    {
                        "command": {
                            "type": "create_course",
                            "data": dict(name="English 101", capacity=33),
                        },
                        "event": CourseCreated(course_name='English 101', capacity=33),
                    },
                    {
                        "command": {
                            "type": "create_course",
                            "data": dict(name="English 101", capacity=33),
                        },
                        "event": {
                            "type": "course_created",
                            "data": CourseCreated(
                                course_name="English 101",
                                capacity=33,
                            ),
                        },
                    },
                ],
            }
        ],
    }
)


def enroll_student(history: list[dict], command): ...


slice_tests.append(
    {
        "test_function": enroll_student,
        "timelines": [
            {
                "timeline_name": "Happy path",
                "checkpoints": [
                    {
                        'command': {'type': 'enroll_student', 'data': dict(name='Bob Marley')},
                        'event': {
                            'type': 'student_enrolled',
                            'data': dict(name='Bob Marley', student_id=create_id("Bob Marley")),
                        },
                    },
                ],
            }
        ],
    }
)


class TestLifecycle(unittest.TestCase):
    def test_slices(self):
        for slice in slice_tests:

            def run_slice_test(events, checkpoint):
                if checkpoint["command"]:  # Change state test
                    if checkpoint["event"] and "exception" not in checkpoint:  # Test success
                        result = slice["test_function"](events, checkpoint["command"]["data"])
                        details = result.get_details()
                        assert details == checkpoint["event"].get_details()
                    elif checkpoint["exception"] and "event" not in checkpoint:  # Test exception
                        try:
                            slice["test_function"](events, checkpoint["command"])
                        except Exception as e:
                            assert checkpoint["exception"].message == e.message
                        raise ValueError(f"{checkpoint['name']} should have thrown exceptions")
                    else:
                        raise ValueError("Bad checkpoint structure")
                else:  # State view test
                    result = slice["test_function"](events)
                    assert result == checkpoint["state"]
                if checkpoint["event"]:
                    events.append(checkpoint["event"])
                    return events

            for timeline in slice["timelines"]:
                functools.reduce(run_slice_test, timeline["checkpoints"], [])

        self.assertTrue(True)


if __name__ == "__main__":
    unittest.main()
