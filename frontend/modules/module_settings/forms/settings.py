from django import forms

class GeneralSettingsForm(forms.Form):
    system_name = forms.CharField(max_length=255)
    language = forms.ChoiceField(choices=[('ar','العربية'),('en','English'),('ur','اردو')])
    timezone = forms.ChoiceField(choices=[('Asia/Riyadh','الرياض'),('Asia/Dubai','دبي')])
    date_format = forms.ChoiceField(choices=[('DD/MM/YYYY','DD/MM/YYYY'),('YYYY-MM-DD','YYYY-MM-DD')])
    time_format = forms.ChoiceField(choices=[('24','24 ساعة'),('12','12 ساعة')])
    items_per_page = forms.ChoiceField(choices=[('10','10'),('20','20'),('50','50'),('100','100')])
