import { useState } from 'react';
import { Activity, Plus, Printer, Save } from 'lucide-react';
import { TransposedTable } from '@/app/components/TransposedTable';

interface PregnancyRecord {
  no: number;
  modeOfConception: string;
  modeOfDelivery: string;
  sexAge: string;
  aliveDead: string;
  abortion: string;
  birthWt: string;
  year: string;
  breastFeeding: string;
  anomalies: string;
}

export function DoctorReportCard() {
  const [patientData, setPatientData] = useState({
    // Text fields
    patientName: 'John Doe',
    patientId: 'PAT-2026-001',
    address: '123 Medical Street, Healthcare City',
    medicalHistory: 'Patient reports occasional headaches. No significant past surgeries.',
    
    // Numerical fields
    height: '175',
    weight: '70',
    age: '45',
    bloodPressureSystolic: '120',
    bloodPressureDiastolic: '80',
    
    // Boolean fields
    diabetes: false,
    hypertension: false,
    allergies: true,
    smokingStatus: false,
  });

  const [pregnancyHistory] = useState<PregnancyRecord[]>([
    {
      no: 1,
      modeOfConception: 'Natural',
      modeOfDelivery: 'Normal Vaginal',
      sexAge: 'Male/5yrs',
      aliveDead: 'Alive',
      abortion: 'No',
      birthWt: '3.2',
      year: '2021',
      breastFeeding: 'Yes - 6mo',
      anomalies: 'None',
    },
    {
      no: 2,
      modeOfConception: 'Natural',
      modeOfDelivery: 'C-Section',
      sexAge: 'Female/2yrs',
      aliveDead: 'Alive',
      abortion: 'No',
      birthWt: '3.5',
      year: '2024',
      breastFeeding: 'Yes - 12mo',
      anomalies: 'None',
    },
  ]);

  const pregnancyColumns = [
    { header: 'No.', key: 'no' },
    { header: 'Mode of Conception', key: 'modeOfConception' },
    { header: 'Mode of Delivery', key: 'modeOfDelivery' },
    { header: 'Sex/Age', key: 'sexAge' },
    { header: 'Alive/Dead', key: 'aliveDead' },
    { header: 'Abortion', key: 'abortion' },
    { header: 'Birth Wt/Kg', key: 'birthWt' },
    { header: 'Year', key: 'year' },
    { header: 'Breast Feeding', key: 'breastFeeding' },
    { header: 'Anomalies/Com', key: 'anomalies' },
  ];

  const handleInputChange = (field: string, value: any) => {
    setPatientData(prev => ({ ...prev, [field]: value }));
  };

  return (
    <div className="min-h-screen bg-[var(--medical-cream)] p-8">
      <div className="max-w-[1200px] mx-auto bg-white shadow-2xl rounded-lg overflow-hidden">
        {/* Letterhead */}
        <div className="bg-[var(--medical-navy)] text-white p-8">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              {/* Logo placeholder */}
              <div className="w-20 h-20 bg-[var(--medical-teal)] rounded-full flex items-center justify-center">
                <Activity className="w-10 h-10 text-white" />
              </div>
              <div>
                <h1 className="text-3xl text-white">HealthCare Medical Center</h1>
                <p className="text-[var(--medical-cream)] mt-1">
                  Excellence in Patient Care | Est. 1995
                </p>
              </div>
            </div>
            <div className="text-right text-sm text-[var(--medical-cream)]">
              <p>456 Hospital Avenue</p>
              <p>Medical District, MD 12345</p>
              <p>Phone: (555) 123-4567</p>
              <p>Fax: (555) 123-4568</p>
            </div>
          </div>
        </div>

        {/* Action Buttons */}
        <div className="bg-[var(--medical-teal)] px-8 py-3 flex justify-end gap-3">
          <button className="flex items-center gap-2 bg-white text-[var(--medical-navy)] px-4 py-2 rounded hover:bg-[var(--medical-cream)] transition">
            <Save className="w-4 h-4" />
            Save
          </button>
          <button className="flex items-center gap-2 bg-white text-[var(--medical-navy)] px-4 py-2 rounded hover:bg-[var(--medical-cream)] transition">
            <Printer className="w-4 h-4" />
            Print
          </button>
        </div>

        {/* Report Content */}
        <div className="p-8">
          {/* Report Title */}
          <div className="border-b-2 border-[var(--medical-teal)] pb-4 mb-6">
            <h2 className="text-2xl text-[var(--medical-navy)]">Patient Medical Report</h2>
            <p className="text-gray-600 mt-1">Date: {new Date().toLocaleDateString()}</p>
          </div>

          {/* Patient Information Section */}
          <div className="mb-8">
            <h3 className="text-xl text-[var(--medical-navy)] mb-4 pb-2 border-b border-[var(--medical-sea-green)]">
              Patient Information
            </h3>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              {/* Text Fields */}
              <div>
                <label className="block text-[var(--medical-navy)] mb-2">
                  Patient Name
                </label>
                <input
                  type="text"
                  value={patientData.patientName}
                  onChange={(e) => handleInputChange('patientName', e.target.value)}
                  className="w-full px-4 py-2 border border-gray-300 rounded focus:outline-none focus:border-[var(--medical-teal)]"
                />
              </div>

              <div>
                <label className="block text-[var(--medical-navy)] mb-2">
                  Patient ID
                </label>
                <input
                  type="text"
                  value={patientData.patientId}
                  onChange={(e) => handleInputChange('patientId', e.target.value)}
                  className="w-full px-4 py-2 border border-gray-300 rounded focus:outline-none focus:border-[var(--medical-teal)]"
                />
              </div>

              <div className="md:col-span-2">
                <label className="block text-[var(--medical-navy)] mb-2">
                  Address
                </label>
                <input
                  type="text"
                  value={patientData.address}
                  onChange={(e) => handleInputChange('address', e.target.value)}
                  className="w-full px-4 py-2 border border-gray-300 rounded focus:outline-none focus:border-[var(--medical-teal)]"
                />
              </div>
            </div>
          </div>

          {/* Vital Statistics - Numerical Fields */}
          <div className="mb-8">
            <h3 className="text-xl text-[var(--medical-navy)] mb-4 pb-2 border-b border-[var(--medical-sea-green)]">
              Vital Statistics
            </h3>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-6">
              <div>
                <label className="block text-[var(--medical-navy)] mb-2">
                  Age (years)
                </label>
                <input
                  type="number"
                  value={patientData.age}
                  onChange={(e) => handleInputChange('age', e.target.value)}
                  className="w-full px-4 py-2 border border-gray-300 rounded focus:outline-none focus:border-[var(--medical-teal)]"
                />
              </div>

              <div>
                <label className="block text-[var(--medical-navy)] mb-2">
                  Height (cm)
                </label>
                <input
                  type="number"
                  value={patientData.height}
                  onChange={(e) => handleInputChange('height', e.target.value)}
                  className="w-full px-4 py-2 border border-gray-300 rounded focus:outline-none focus:border-[var(--medical-teal)]"
                />
              </div>

              <div>
                <label className="block text-[var(--medical-navy)] mb-2">
                  Weight (kg)
                </label>
                <input
                  type="number"
                  value={patientData.weight}
                  onChange={(e) => handleInputChange('weight', e.target.value)}
                  className="w-full px-4 py-2 border border-gray-300 rounded focus:outline-none focus:border-[var(--medical-teal)]"
                />
              </div>

              <div>
                <label className="block text-[var(--medical-navy)] mb-2">
                  BMI
                </label>
                <input
                  type="text"
                  value={(
                    parseFloat(patientData.weight) /
                    Math.pow(parseFloat(patientData.height) / 100, 2)
                  ).toFixed(1)}
                  disabled
                  className="w-full px-4 py-2 border border-gray-300 rounded bg-gray-50"
                />
              </div>

              <div className="md:col-span-2">
                <label className="block text-[var(--medical-navy)] mb-2">
                  Blood Pressure (mmHg)
                </label>
                <div className="flex gap-2 items-center">
                  <input
                    type="number"
                    value={patientData.bloodPressureSystolic}
                    onChange={(e) => handleInputChange('bloodPressureSystolic', e.target.value)}
                    placeholder="Systolic"
                    className="w-full px-4 py-2 border border-gray-300 rounded focus:outline-none focus:border-[var(--medical-teal)]"
                  />
                  <span className="text-[var(--medical-navy)]">/</span>
                  <input
                    type="number"
                    value={patientData.bloodPressureDiastolic}
                    onChange={(e) => handleInputChange('bloodPressureDiastolic', e.target.value)}
                    placeholder="Diastolic"
                    className="w-full px-4 py-2 border border-gray-300 rounded focus:outline-none focus:border-[var(--medical-teal)]"
                  />
                </div>
              </div>
            </div>
          </div>

          {/* Medical Conditions - Boolean Fields */}
          <div className="mb-8">
            <h3 className="text-xl text-[var(--medical-navy)] mb-4 pb-2 border-b border-[var(--medical-sea-green)]">
              Medical Conditions
            </h3>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="flex items-center justify-between p-4 border border-gray-300 rounded hover:border-[var(--medical-teal)] transition">
                <label className="text-[var(--medical-navy)]">
                  Diabetes
                </label>
                <div className="flex gap-4">
                  <button
                    onClick={() => handleInputChange('diabetes', true)}
                    className={`px-6 py-2 rounded transition ${
                      patientData.diabetes
                        ? 'bg-[var(--medical-teal)] text-white'
                        : 'bg-gray-200 text-gray-700 hover:bg-[var(--medical-sea-green)] hover:text-white'
                    }`}
                  >
                    Yes
                  </button>
                  <button
                    onClick={() => handleInputChange('diabetes', false)}
                    className={`px-6 py-2 rounded transition ${
                      !patientData.diabetes
                        ? 'bg-[var(--medical-teal)] text-white'
                        : 'bg-gray-200 text-gray-700 hover:bg-[var(--medical-sea-green)] hover:text-white'
                    }`}
                  >
                    No
                  </button>
                </div>
              </div>

              <div className="flex items-center justify-between p-4 border border-gray-300 rounded hover:border-[var(--medical-teal)] transition">
                <label className="text-[var(--medical-navy)]">
                  Hypertension
                </label>
                <div className="flex gap-4">
                  <button
                    onClick={() => handleInputChange('hypertension', true)}
                    className={`px-6 py-2 rounded transition ${
                      patientData.hypertension
                        ? 'bg-[var(--medical-teal)] text-white'
                        : 'bg-gray-200 text-gray-700 hover:bg-[var(--medical-sea-green)] hover:text-white'
                    }`}
                  >
                    Yes
                  </button>
                  <button
                    onClick={() => handleInputChange('hypertension', false)}
                    className={`px-6 py-2 rounded transition ${
                      !patientData.hypertension
                        ? 'bg-[var(--medical-teal)] text-white'
                        : 'bg-gray-200 text-gray-700 hover:bg-[var(--medical-sea-green)] hover:text-white'
                    }`}
                  >
                    No
                  </button>
                </div>
              </div>

              <div className="flex items-center justify-between p-4 border border-gray-300 rounded hover:border-[var(--medical-teal)] transition">
                <label className="text-[var(--medical-navy)]">
                  Known Allergies
                </label>
                <div className="flex gap-4">
                  <button
                    onClick={() => handleInputChange('allergies', true)}
                    className={`px-6 py-2 rounded transition ${
                      patientData.allergies
                        ? 'bg-[var(--medical-teal)] text-white'
                        : 'bg-gray-200 text-gray-700 hover:bg-[var(--medical-sea-green)] hover:text-white'
                    }`}
                  >
                    Yes
                  </button>
                  <button
                    onClick={() => handleInputChange('allergies', false)}
                    className={`px-6 py-2 rounded transition ${
                      !patientData.allergies
                        ? 'bg-[var(--medical-teal)] text-white'
                        : 'bg-gray-200 text-gray-700 hover:bg-[var(--medical-sea-green)] hover:text-white'
                    }`}
                  >
                    No
                  </button>
                </div>
              </div>

              <div className="flex items-center justify-between p-4 border border-gray-300 rounded hover:border-[var(--medical-teal)] transition">
                <label className="text-[var(--medical-navy)]">
                  Smoking Status
                </label>
                <div className="flex gap-4">
                  <button
                    onClick={() => handleInputChange('smokingStatus', true)}
                    className={`px-6 py-2 rounded transition ${
                      patientData.smokingStatus
                        ? 'bg-[var(--medical-teal)] text-white'
                        : 'bg-gray-200 text-gray-700 hover:bg-[var(--medical-sea-green)] hover:text-white'
                    }`}
                  >
                    Yes
                  </button>
                  <button
                    onClick={() => handleInputChange('smokingStatus', false)}
                    className={`px-6 py-2 rounded transition ${
                      !patientData.smokingStatus
                        ? 'bg-[var(--medical-teal)] text-white'
                        : 'bg-gray-200 text-gray-700 hover:bg-[var(--medical-sea-green)] hover:text-white'
                    }`}
                  >
                    No
                  </button>
                </div>
              </div>
            </div>
          </div>

          {/* Medical History - Text Area */}
          <div className="mb-8">
            <h3 className="text-xl text-[var(--medical-navy)] mb-4 pb-2 border-b border-[var(--medical-sea-green)]">
              Previous Medical History
            </h3>
            <textarea
              value={patientData.medicalHistory}
              onChange={(e) => handleInputChange('medicalHistory', e.target.value)}
              rows={6}
              className="w-full px-4 py-3 border border-gray-300 rounded focus:outline-none focus:border-[var(--medical-teal)] resize-none"
              placeholder="Enter detailed medical history..."
            />
          </div>

          {/* Pregnancy History Table - Transposed */}
          <div className="mb-8">
            <div className="flex items-center justify-between mb-4 pb-2 border-b border-[var(--medical-sea-green)]">
              <h3 className="text-xl text-[var(--medical-navy)]">
                Obstetric History (Past Pregnancies)
              </h3>
              <button className="flex items-center gap-2 bg-[var(--medical-teal)] text-white px-4 py-2 rounded hover:bg-[var(--medical-sea-green)] transition">
                <Plus className="w-4 h-4" />
                Add Record
              </button>
            </div>
            <p className="text-sm text-gray-600 mb-4 italic">
              *Wide tables are displayed in transposed format for better readability
            </p>
            <TransposedTable columns={pregnancyColumns} data={pregnancyHistory} />
          </div>

          {/* Additional Notes Section */}
          <div className="mb-8">
            <h3 className="text-xl text-[var(--medical-navy)] mb-4 pb-2 border-b border-[var(--medical-sea-green)]">
              Additional Notes / Observations
            </h3>
            <textarea
              rows={4}
              className="w-full px-4 py-3 border border-gray-300 rounded focus:outline-none focus:border-[var(--medical-teal)] resize-none"
              placeholder="Enter any additional observations or notes..."
            />
          </div>

          {/* Physician Signature */}
          <div className="border-t-2 border-[var(--medical-navy)] pt-6 mt-8">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
              <div>
                <label className="block text-[var(--medical-navy)] mb-2">
                  Physician Name
                </label>
                <input
                  type="text"
                  placeholder="Dr. Jane Smith"
                  className="w-full px-4 py-2 border border-gray-300 rounded focus:outline-none focus:border-[var(--medical-teal)]"
                />
              </div>
              <div>
                <label className="block text-[var(--medical-navy)] mb-2">
                  License Number
                </label>
                <input
                  type="text"
                  placeholder="MD-12345"
                  className="w-full px-4 py-2 border border-gray-300 rounded focus:outline-none focus:border-[var(--medical-teal)]"
                />
              </div>
              <div>
                <label className="block text-[var(--medical-navy)] mb-2">
                  Date
                </label>
                <input
                  type="date"
                  defaultValue={new Date().toISOString().split('T')[0]}
                  className="w-full px-4 py-2 border border-gray-300 rounded focus:outline-none focus:border-[var(--medical-teal)]"
                />
              </div>
              <div>
                <label className="block text-[var(--medical-navy)] mb-2">
                  Digital Signature
                </label>
                <div className="w-full h-[42px] border-2 border-dashed border-[var(--medical-teal)] rounded flex items-center justify-center text-gray-500 hover:bg-[var(--medical-cream)] transition cursor-pointer">
                  Click to sign
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Footer */}
        <div className="bg-[var(--medical-navy)] text-white px-8 py-4 text-center text-sm">
          <p className="text-[var(--medical-cream)]">
            This is a confidential medical document. Unauthorized disclosure is prohibited.
          </p>
          <p className="text-[var(--medical-cream)] mt-1">
            © 2026 HealthCare Medical Center. All rights reserved.
          </p>
        </div>
      </div>
    </div>
  );
}
