# count_orders_per_domain.py
import requests
import json
from datetime import datetime
from typing import List, Dict
import time


class DomainCounter:
    """Счетчик заявок по доменам"""

    def __init__(self):
        self.base_domain = 'https://main.techlegal.ru'
        self.resource = 'api'
        self.token = "API_KEY"
        self.stats = {}

    def create_client(self):
        """Создание HTTP клиента"""
        client = requests.Session()
        client.timeout = 30
        return client

    def get_all_domains(self) -> List[str]:
        """Получить список всех доменов"""
        client = self.create_client()
        url = f'{self.base_domain}/{self.resource}/getRequestFsspResponseCountDomain'
        payload = {'token': self.token}

        try:
            response = client.post(url, payload, timeout=30)
            if response.status_code == 200:
                domains = [el['domain'] for el in response.json()]
                print(f'✅ Получено доменов: {len(domains)}')
                return domains
        except Exception as e:
            print(f'❌ Ошибка получения доменов: {e}')
        finally:
            client.close()

        return []

    def count_orders_on_domain(self, domain: str) -> Dict:
        """Подсчитать количество заявок на домене"""
        client = self.create_client()
        print(f"\n🔍 Подсчет на домене: {domain}")

        try:
            total_count = 0
            offset = 0
            batch_size = 1000  # Размер страницы
            page_num = 0
            consecutive_empty_pages = 0  # Счетчик подряд идущих пустых страниц
            max_consecutive_empty = 3  # Максимум 3 пустых страницы подряд

            start_time = time.time()

            while True:
                page_num += 1

                # Запрос страницы
                url = f'{domain.rstrip("/")}/{self.resource}/getRequestFsspResponse'
                payload = {
                    'token': self.token,
                    'count': batch_size,
                    'isSqueezeText': 1,
                    'offset': offset
                }

                try:
                    response = client.post(url, payload, timeout=30)

                    if response.status_code != 200:
                        print(f"    ❌ HTTP {response.status_code} на странице {page_num}: {response.text[:200]}")
                        break

                    data = response.json()

                    if isinstance(data, list):
                        batch_count = len(data)
                        total_count += batch_count

                        if batch_count > 0:
                            print(f"    📄 Страница {page_num}: {batch_count} заявок (всего: {total_count:,})")
                            consecutive_empty_pages = 0  # Сбрасываем счетчик пустых страниц
                        else:
                            print(f"    📄 Страница {page_num}: пусто")
                            consecutive_empty_pages += 1

                            # Если несколько пустых страниц подряд, считаем что данные закончились
                            if consecutive_empty_pages >= max_consecutive_empty:
                                print(f"    ✅ {max_consecutive_empty} пустых страниц подряд - конец данных")
                                # Откатываем счетчик пустых страниц
                                total_count -= (consecutive_empty_pages - 1) * batch_size
                                break

                        # Проверяем условие выхода по количеству записей
                        if batch_count < batch_size and batch_count > 0:
                            # Получили меньше записей чем запрашивали, значит это последняя страница
                            print(f"    ✅ Последняя страница (получено {batch_count} из {batch_size})")
                            break

                        # Если получили ровно batch_size записей, продолжаем
                        elif batch_count == batch_size:
                            # Продолжаем получать следующую страницу
                            offset += batch_size
                        else:
                            # batch_count = 0, но меньше max_consecutive_empty - продолжаем
                            offset += batch_size

                    else:
                        print(f"    ⚠ Ответ не список, тип: {type(data)}")
                        print(f"    Содержимое: {str(data)[:200]}")
                        break

                except requests.exceptions.Timeout:
                    print(f"    ⏱️  Таймаут на странице {page_num}")
                    break
                except requests.exceptions.ConnectionError:
                    print(f"    🔌 Ошибка соединения на странице {page_num}")
                    break
                except json.JSONDecodeError:
                    print(f"    📄 Ошибка парсинга JSON на странице {page_num}")
                    break
                except Exception as e:
                    print(f"    ❌ Ошибка запроса страницы {page_num}: {type(e).__name__} - {str(e)[:100]}")
                    break

                # Пауза чтобы не перегружать API
                if page_num % 10 == 0:
                    time.sleep(1)
                elif page_num % 5 == 0:
                    time.sleep(0.5)

            elapsed_time = time.time() - start_time

            result = {
                'domain': domain,
                'total_orders': total_count,
                'pages_processed': page_num,
                'time_spent_seconds': round(elapsed_time, 1),
                'status': 'success',
                'avg_speed': round(total_count / elapsed_time, 1) if elapsed_time > 0 else 0
            }

            print(f"    📊 Итого: {total_count:,} заявок за {page_num} страниц")
            print(f"    ⏱️  Время: {elapsed_time:.1f} сек ({result['avg_speed']:.1f} заявок/сек)")

            return result

        except Exception as e:
            print(f"    ❌ Критическая ошибка: {type(e).__name__} - {str(e)[:100]}")
            return {
                'domain': domain,
                'total_orders': 0,
                'pages_processed': 0,
                'time_spent_seconds': 0,
                'status': 'error',
                'error': str(e)[:200],
                'avg_speed': 0
            }
        finally:
            client.close()

    def count_all_domains(self, domains: List[str]) -> Dict:
        """Подсчитать заявки на всех доменах"""
        print("=" * 80)
        print("📊 ПОДСЧЕТ ЗАЯВОК ПО ДОМЕНАМ")
        print("=" * 80)

        results = []
        total_all_orders = 0
        start_time = time.time()

        for i, domain in enumerate(domains, 1):
            print(f"\n[{i}/{len(domains)}] ", end="")

            result = self.count_orders_on_domain(domain)
            results.append(result)

            if result['status'] == 'success':
                total_all_orders += result['total_orders']

            # Прогресс
            elapsed = time.time() - start_time
            processed = len([r for r in results if r['status'] == 'success'])
            if processed > 0:
                avg_time_per_domain = elapsed / processed
                remaining = avg_time_per_domain * (len(domains) - i)
            else:
                remaining = 0

            print(f"📈 Прогресс: {i}/{len(domains)} ({i / len(domains) * 100:.1f}%)")
            print(f"⏱️  Прошло: {elapsed:.0f} сек, Осталось: ~{remaining:.0f} сек")

            # Защита от слишком быстрых запросов
            if i < len(domains):
                time.sleep(1)

        # Общая статистика
        elapsed_total = time.time() - start_time

        print("\n" + "=" * 80)
        print("📈 ОБЩАЯ СТАТИСТИКА")
        print("=" * 80)

        # Сортируем по количеству заявок
        sorted_results = sorted(results, key=lambda x: x['total_orders'], reverse=True)

        successful = len([r for r in results if r['status'] == 'success'])
        print(f"🌐 Всего доменов: {len(domains)}")
        print(f"✅ Успешно обработано: {successful}")
        print(f"❌ С ошибками: {len(domains) - successful}")
        print(f"📊 Всего заявок: {total_all_orders:,}")
        print(f"⏱️  Общее время: {elapsed_total:.1f} сек")
        print(
            f"⚡ Средняя скорость: {total_all_orders / elapsed_total:.1f} заявок/сек" if elapsed_total > 0 else "⚡ Средняя скорость: N/A")

        print("\n🏆 ТОП-10 доменов по количеству заявок:")
        for i, result in enumerate(sorted_results[:10], 1):
            if result['total_orders'] > 0:
                domain_short = result['domain'].replace('https://', '').replace('http://', '').split('/')[0]
                domain_short = domain_short[:40]
                print(
                    f"  {i:2d}. {domain_short:40} : {result['total_orders']:8,} заявок ({result['pages_processed']} стр.)")

        print("\n📋 Домены БЕЗ заявок:")
        empty_domains = [r for r in sorted_results if r['total_orders'] == 0 and r['status'] == 'success']
        for i, result in enumerate(empty_domains[:20], 1):
            domain_short = result['domain'].replace('https://', '').replace('http://', '').split('/')[0]
            domain_short = domain_short[:40]
            print(f"  {i:2d}. {domain_short}")

        if len(empty_domains) > 20:
            print(f"    ... и еще {len(empty_domains) - 20} доменов")

        print("\n❌ Домены с ошибками:")
        error_domains = [r for r in sorted_results if r['status'] == 'error']
        for i, result in enumerate(error_domains[:10], 1):
            domain_short = result['domain'].replace('https://', '').replace('http://', '').split('/')[0]
            domain_short = domain_short[:40]
            error_msg = result.get('error', 'неизвестная ошибка')[:50]
            print(f"  {i:2d}. {domain_short} : {error_msg}")

        if len(error_domains) > 10:
            print(f"    ... и еще {len(error_domains) - 10} доменов")

        # Сохраняем результаты
        self.save_results(results, total_all_orders, elapsed_total)

        return {
            'total_domains': len(domains),
            'successful_domains': successful,
            'error_domains': len(error_domains),
            'total_orders': total_all_orders,
            'results': results,
            'time_total': elapsed_total
        }

    def save_results(self, results: List[Dict], total_orders: int, elapsed_time: float):
        """Сохранить результаты в файл"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"data/domain_stats_{timestamp}.json"

        # Создаем папку если нет
        import os
        os.makedirs('data', exist_ok=True)

        successful = len([r for r in results if r['status'] == 'success'])

        stats = {
            'время_запуска': datetime.now().isoformat(),
            'всего_доменов': len(results),
            'успешно_обработано': successful,
            'с_ошибками': len(results) - successful,
            'всего_заявок': total_orders,
            'общее_время_сек': round(elapsed_time, 1),
            'средняя_скорость': round(total_orders / elapsed_time, 2) if elapsed_time > 0 else 0,
            'результаты_по_доменам': results
        }

        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(stats, f, ensure_ascii=False, indent=2)

            print(f"\n💾 Результаты сохранены: {filename}")

            # Также сохраняем в CSV для Excel
            csv_filename = f"data/domain_stats_{timestamp}.csv"
            self.save_to_csv(results, csv_filename)

        except Exception as e:
            print(f"⚠ Ошибка сохранения: {e}")

    def save_to_csv(self, results: List[Dict], filename: str):
        """Сохранить в CSV"""
        try:
            import csv

            with open(filename, 'w', encoding='utf-8', newline='') as f:
                writer = csv.writer(f)
                # Заголовки
                writer.writerow(
                    ['№', 'Домен', 'Заявок', 'Страниц', 'Время (сек)', 'Скорость (заявок/сек)', 'Статус', 'Ошибка'])

                # Данные
                for i, result in enumerate(sorted(results, key=lambda x: x['total_orders'], reverse=True), 1):
                    writer.writerow([
                        i,
                        result['domain'],
                        result['total_orders'],
                        result['pages_processed'],
                        result['time_spent_seconds'],
                        result.get('avg_speed', 0),
                        result['status'],
                        result.get('error', '')
                    ])

            print(f"📄 CSV файл: {filename}")

        except Exception as e:
            print(f"⚠ Ошибка сохранения CSV: {e}")


def main():
    print("=" * 80)
    print("🔍 ПОДСЧЕТ ЗАЯВОК ПО ВСЕМ ДОМЕНАМ")
    print("=" * 80)

    # Инициализация
    counter = DomainCounter()

    # Получаем домены
    print("\n📥 Получение списка доменов...")
    domains = counter.get_all_domains()

    if not domains:
        print("❌ Нет доменов для обработки")
        return

    print(f"\n🌐 Найдено {len(domains)} доменов")

    # Показываем примеры
    print("\n📋 ПЕРВЫЕ 5 ДОМЕНОВ:")
    for i, domain in enumerate(domains[:5], 1):
        print(f"  {i}. {domain}")

    if len(domains) > 5:
        print(f"    ... и еще {len(domains) - 5} доменов")

    # Подтверждение
    response = input(f"\nПодсчитать заявки на всех {len(domains)} доменах? (y/n): ")

    if response.lower() != 'y':
        print("Отменено")
        return

    # Можно обрабатывать выборочно
    print("\n🔧 ВАРИАНТЫ ОБРАБОТКИ:")
    print("  1. Все домены")
    print("  2. Первые N доменов")
    print("  3. Выборочные домены")
    print("  4. Тестовый запуск (5 доменов)")

    choice = input("\nВыберите вариант (1-4): ").strip()

    if choice == '2':
        try:
            count = int(input(f"Сколько доменов обработать? (1-{len(domains)}): "))
            count = max(1, min(count, len(domains)))
            selected_domains = domains[:count]
            print(f"⚡ Обрабатываем {count} доменов")
        except:
            print("⚠ Неверный ввод, обрабатываем все домены")
            selected_domains = domains
    elif choice == '3':
        print("\nВведите номера доменов через запятую (например: 1,3,5,10-15):")
        selection = input("Номера: ").strip()

        # Парсим выбор
        selected_indices = set()
        for part in selection.split(','):
            part = part.strip()
            if '-' in part:
                try:
                    start, end = map(int, part.split('-'))
                    selected_indices.update(range(start - 1, end))
                except:
                    print(f"⚠ Неверный диапазон: {part}")
            elif part.isdigit():
                selected_indices.add(int(part) - 1)

        selected_domains = [domains[i] for i in selected_indices if 0 <= i < len(domains)]
        print(f"⚡ Обрабатываем {len(selected_domains)} выбранных доменов")
    elif choice == '4':
        selected_domains = domains[:5]
        print(f"⚡ ТЕСТОВЫЙ РЕЖИМ: Обрабатываем 5 доменов")
    else:
        selected_domains = domains
        print(f"⚡ Обрабатываем ВСЕ {len(domains)} доменов")

    # Обработка
    counter.count_all_domains(selected_domains)

    print("\n" + "=" * 80)
    print("✅ ПОДСЧЕТ ЗАВЕРШЕН")
    print("=" * 80)


if __name__ == '__main__':
    main()
