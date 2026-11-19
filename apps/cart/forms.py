from django import forms


class CheckoutForm(forms.Form):
    full_name = forms.CharField(
        label="نام و نام خانوادگی گیرنده",
        max_length=150,
        widget=forms.TextInput(attrs={
            "class": "form-control",
            "autocomplete": "name",
            "placeholder": "نام کامل گیرنده",
        }),
    )

    phone = forms.CharField(
        label="شماره تماس",
        max_length=11,
        min_length=10,
        widget=forms.TextInput(attrs={
            "class": "form-control",
            "autocomplete": "tel",
            "inputmode": "numeric",
            "placeholder": "مثلاً 09123456789",
        }),
    )

    postal_code = forms.CharField(
        label="کد پستی",
        max_length=10,
        min_length=10,
        widget=forms.TextInput(attrs={
            "class": "form-control",
            "autocomplete": "postal-code",
            "inputmode": "numeric",
            "placeholder": "کد پستی ۱۰ رقمی بدون خط فاصله",
        }),
    )

    address = forms.CharField(
        label="نشانی کامل پستی",
        widget=forms.Textarea(attrs={
            "class": "form-control",
            "rows": 4,
            "autocomplete": "street-address",
            "placeholder": "استان، شهر، خیابان، کوچه، پلاک، واحد",
        }),
    )

    def clean_phone(self):
        phone = self.cleaned_data["phone"].strip().replace(" ", "").replace("-", "")
        translation = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")
        phone = phone.translate(translation)

        if not phone.isdigit() or len(phone) not in (10, 11):
            raise forms.ValidationError("شماره تماس معتبر نیست.")
        return phone

    def clean_postal_code(self):
        postal_code = self.cleaned_data["postal_code"].strip()
        translation = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")
        postal_code = postal_code.translate(translation)

        if not postal_code.isdigit() or len(postal_code) != 10:
            raise forms.ValidationError("کد پستی باید دقیقاً ۱۰ رقم باشد.")
        return postal_code
