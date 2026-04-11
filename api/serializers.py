from rest_framework import serializers
from .models import Lesson

class LessonSerializer(serializers.ModelSerializer):
    # Öğretmenin sadece ID'sini değil, kullanıcı adını da React'e göndermek için:
    teacher_name = serializers.CharField(source='teacher.username', read_only=True)

    class Meta:
        model = Lesson
        fields = ['id', 'title', 'description', 'start_time', 'end_time', 'meet_link', 'teacher_name', 'is_recurring']